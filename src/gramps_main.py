#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2001-2006  Donald N. Allingham
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

# $Id$

#-------------------------------------------------------------------------
#
# GTK+/GNOME modules
#
#-------------------------------------------------------------------------
import gtk
import logging
import os

log = logging.getLogger(".")

#-------------------------------------------------------------------------
#
# GRAMPS  modules
#
#-------------------------------------------------------------------------
import ViewManager
import GrampsDb
import ArgHandler
import Config
import GrampsCfg
import const
import Errors
import TipOfDay
import DataViews
from Mime import mime_type_is_defined
from QuestionDialog import ErrorDialog
from gettext import gettext as _

iconpaths = [const.image_dir,"."]

def register_stock_icons ():
    import os
    items = [
        (os.path.join(const.image_dir,'person.svg'),
         ('gramps-person',_('Person'),gtk.gdk.CONTROL_MASK,0,'')),
        (os.path.join(const.image_dir,'relation.svg'),
         ('gramps-family',_('Relationships'),gtk.gdk.CONTROL_MASK,0,'')),
        (os.path.join(const.image_dir,'flist.svg'),
         ('gramps-family-list',_('Family List'),gtk.gdk.CONTROL_MASK,0,'')),
        (os.path.join(const.image_dir,'media.svg'),
         ('gramps-media',_('Media'),gtk.gdk.CONTROL_MASK,0,'')),
        (os.path.join(const.image_dir,'ped24.png'),
         ('gramps-pedigree',_('Pedigree'),gtk.gdk.CONTROL_MASK,0,'')),
        (os.path.join(const.image_dir,'repos.png'),
         ('gramps-repository',_('Repositories'),gtk.gdk.CONTROL_MASK,0,'')),
        (os.path.join(const.image_dir,'sources.png'),
         ('gramps-source',_('Sources'),gtk.gdk.CONTROL_MASK,0,'')),
        (os.path.join(const.image_dir,'events.png'),
         ('gramps-event',_('Events'),gtk.gdk.CONTROL_MASK,0,'')),
        (os.path.join(const.image_dir,'place.png'),
         ('gramps-place',_('Places'),gtk.gdk.CONTROL_MASK,0,'')),
        (os.path.join(const.image_dir,'place.png'),
         ('gramps-map',_('Map'),gtk.gdk.CONTROL_MASK,0,'')),
        ]
    
    # Register our stock items
    gtk.stock_add (map(lambda x: x[1],items))
    
    # Add our custom icon factory to the list of defaults
    factory = gtk.IconFactory ()
    factory.add_default ()
    
    for (key,data) in items:

        for dirname in iconpaths:
            icon_file = os.path.expanduser(os.path.join(dirname,key))
            if os.path.isfile(icon_file):
                try:
                    pixbuf = gtk.gdk.pixbuf_new_from_file (icon_file)
                    break
                except:
                    pass
        else:
            icon_file = os.path.join(const.image_dir,'gramps.png')
            pixbuf = gtk.gdk.pixbuf_new_from_file (icon_file)
            
        pixbuf = pixbuf.add_alpha(True, chr(0xff), chr(0xff), chr(0xff))

        icon_set = gtk.IconSet (pixbuf)
        factory.add (data[0], icon_set)


def build_user_paths():
    user_paths = [const.home_dir,
                  os.path.join(const.home_dir,"filters"),
                  os.path.join(const.home_dir,"plugins"),
                  os.path.join(const.home_dir,"templates"),
                  os.path.join(const.home_dir,"thumb")]
    
    for path in user_paths:
        if not os.path.isdir(path):
            os.mkdir(path)


class Gramps:
    """
    Main class corresponding to a running gramps process.

    There can be only one instance of this class per gramps application
    process. It may spawn several windows and control several databases.
    """

    def __init__(self,args):
        try:
            build_user_paths()
            self.welcome()    
        except OSError, msg:
            ErrorDialog(_("Configuration error"),str(msg))
            return
        except Errors.GConfSchemaError, val:
            ErrorDialog(_("Configuration error"),str(val) +
                        _("\n\nPossibly the installation of GRAMPS "
                          "was incomplete. Make sure the GConf schema "
                          "of GRAMPS is properly installed."))
            gtk.main_quit()
            return
        except:
            log.error("Error reading configuration.", exc_info=True)
            return
            
        if not mime_type_is_defined(const.app_gramps):
            ErrorDialog(_("Configuration error"),
                        _("A definition for the MIME-type %s could not "
                          "be found \n\nPossibly the installation of GRAMPS "
                          "was incomplete. Make sure the MIME-types "
                          "of GRAMPS are properly installed.")
                        % const.app_gramps)
            gtk.main_quit()
            return


        register_stock_icons()
        
        state = GrampsDb.DbState()
        self.vm = ViewManager.ViewManager(state)
        for view in DataViews.get_views():
            self.vm.register_view(view)

        ArgHandler.ArgHandler(state,self.vm,args)

        self.vm.init_interface()
        state.db.request_rebuild()
        state.change_active_person(state.db.get_default_person())
        
        # Don't show main window until ArgHandler is done.
        # This prevents a window from annoyingly popping up when
        # the command line args are sufficient to operate without it.
        Config.client.notify_add("/apps/gramps/researcher",
                                 self.researcher_key_update)
        Config.client.notify_add("/apps/gramps/interface/statusbar",
                                 self.statusbar_key_update)
        Config.client.notify_add("/apps/gramps/interface/toolbar",
                                 self.toolbar_key_update)
#        Config.client.notify_add("/apps/gramps/interface/toolbar-on",
#                                 self.toolbar_on_key_update)
#        Config.client.notify_add("/apps/gramps/interface/filter",
#                                    self.filter_key_update)
#        Config.client.notify_add("/apps/gramps/interface/view",
#                                    self.sidebar_key_update)
#        Config.client.notify_add("/apps/gramps/preferences/name-format",
#                                    self.familyview_key_update)
#        Config.client.notify_add("/apps/gramps/preferences/date-format",
#                                    self.date_format_key_update)

        if Config.get(Config.USE_TIPS):
            TipOfDay.TipOfDay(self.vm.uistate)

##         # FIXME: THESE will have to be added (ViewManager?)
##         # once bookmarks work again
##         self.db.set_researcher(GrampsCfg.get_researcher())
##         self.db.connect('person-delete',self.on_remove_bookmark)
##         self.db.connect('person-update',self.on_update_bookmark)

    def welcome(self):
        return

    def researcher_key_update(self,client,cnxn_id,entry,data):
        pass
#         self.db.set_person_id_prefix(Config.get(Config.IPREFIX))
#         self.db.set_family_id_prefix(Config.get(Config.FPREFIX))
#         self.db.set_source_id_prefix(Config.get(Config.SPREFIX))
#         self.db.set_object_id_prefix(Config.get(Config.OPREFIX))
#         self.db.set_place_id_prefix(Config.get(Config.PPREFIX))
#         self.db.set_event_id_prefix(Config.get(Config.EPREFIX))

    def statusbar_key_update(self,client,cnxn_id,entry,data):
        self.vm.uistate.modify_statusbar()

    def toolbar_key_update(self,client,cnxn_id,entry,data):
        the_style = Config.get(Config.TOOLBAR)
        if the_style == -1:
            self.vm.toolbar.unset_style()
        else:
            self.vm.toolbar.set_style(the_style)

#     def toolbar_on_key_update(self,client,cnxn_id,entry,data):
#         is_on = COnfig.get_toolbar_on()
#         self.enable_toolbar(is_on)
