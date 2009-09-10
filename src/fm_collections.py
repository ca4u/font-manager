# Font Manager, a font management application for the GNOME desktop
#
# Copyright (C) 2008 Karl Pickett <http://fontmanager.blogspot.com/>
# Copyright (C) 2009 Jerry Casiano
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
# MA 02110-1301, USA.

import os
import gtk
import gobject
import libxml2
import logging

from os.path import exists

import config
import xmlconf
import stores
from fontload import g_fonts
from stores import Collection


collection_ls = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_PYOBJECT, 
                gobject.TYPE_STRING)
                
family_ls = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_PYOBJECT, 
                gobject.TYPE_STRING)
                
collection_tv = gtk.TreeView()

family_tv = gtk.TreeView()

collections = []

FM_DIR                  =       os.getenv("HOME") + "/.FontManager"
FM_GROUP_CONF           =       os.path.join(FM_DIR, "groups.xml")
FM_GROUP_CONF_BACKUP    =       FM_GROUP_CONF + ".bak"

class Collections:
        
    def update_views(self):
        self.update_collection_view()
        self.update_font_view()
        
    def update_collection_view(self):
        
        for c in collections:
            c.set_enabled_from_fonts()

        model = collection_tv.get_model()
        iter = model.get_iter_first()
        while iter:
            label, obj = model.get(iter, 0, 1)
            if not obj:
                iter = model.iter_next(iter)
                continue
            if obj in collections:
                new_label = obj.get_label()
                if label != new_label:
                    model.set(iter, 0, new_label)
                iter = model.iter_next(iter)
            else: 
                if not model.remove(iter): return

    def update_font_view(self):
        c = self.get_current_collection()
        model = family_tv.get_model()
        iter = model.get_iter_first()
        while iter:
            label, obj = model.get(iter, 0, 1)
            if obj in c.fonts:
                new_label = obj.get_label()
                if label != new_label:
                    model.set(iter, 0, new_label)
                iter = model.iter_next(iter)
            else: 
                if not model.remove(iter): return
                
    def get_new_collection_name(self, widget, old_name):
        d = gtk.Dialog(_("Enter Collection Name"), 
                widget, gtk.DIALOG_MODAL,
                (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                    gtk.STOCK_OK, gtk.RESPONSE_OK))
        d.set_default_size(325, 50)
        d.set_default_response(gtk.RESPONSE_OK)
        text = gtk.Entry()
        if old_name:
            text.set_text(old_name)
        text.set_property("activates-default", True)
        d.vbox.pack_start(text)
        text.show()
        ret = d.run()
        d.destroy()
        if ret == gtk.RESPONSE_OK:
            return text.get_text().strip()
        return None

    def create_collections(self):
        
        from fontload import g_fonts
        
        c = Collection(_("All Fonts"))
        for f in sorted(g_fonts.itervalues(), stores.cmp_family):
            c.fonts.append(f)
        self.add_collection(c)

        c = Collection(_("System"))
        for f in sorted(g_fonts.itervalues(), stores.cmp_family):
            if not f.user:
                c.fonts.append(f)
        self.add_collection(c)

        c = Collection(_("User"))
        for f in sorted(g_fonts.itervalues(), stores.cmp_family):
            if f.user:
                c.fonts.append(f)
        self.add_collection(c)

        # add separator between builtins and user collections
        lstore = collection_tv.get_model()
        iter = lstore.append()
        lstore.set(iter, 1, None)

        # XXX  need to add a category containing 
        # any enabled fonts not in a collection
        
        self.load_user_collections()

    def add_collection(self, c):
        c.set_enabled_from_fonts()
        lstore = collection_tv.get_model()
        iter = lstore.append()
        lstore.set(iter, 0, c.get_label())
        lstore.set(iter, 1, c)
        lstore.set(iter, 2, c.get_text())
        collections.append(c)

    def add_font_to_view(self, f):
        lstore = family_tv.get_model()
        iter = lstore.append(None)
        lstore.set(iter, 0, f.get_label())
        lstore.set(iter, 1, f) 
        lstore.set(iter, 2, f.family) 

    def show_collection(self, c):
        lstore = family_tv.get_model()
        lstore.clear()
        if not c:
            return
        for f in c.fonts:
            self.add_font_to_view(f)

    def collection_name_exists(self, name):
        for c in collections:
            if c.name == name:
                return True
        return False

    def add_new_collection(self, widget):
        str = _("New Collection")
        while True:
            str = self.get_new_collection_name(widget, str)
            if not str:
                return
            if not self.collection_name_exists(str):
                break
        c = Collection(str)
        c.builtin = False
        self.add_collection(c)
        
    def delete_collection(self):
        c = self.get_current_collection()
        collections.remove(c)
        self.update_views()

    def collection_activated(self, tv, path, col):
        c = self.get_current_collection()
        self.enable_collection(not c.enabled)

    def enable_collection(self, enabled):
        c = self.get_current_collection()
        if enabled == True:
            if c.builtin and not self.confirm_enable_collection(enabled):
                return
            c.set_enabled(enabled)
            self.update_views()
            xmlconf.save_blacklist()
        elif enabled == False:
            if c.builtin and not self.confirm_enable_collection(enabled):
                return
            c.set_enabled(enabled)
            self.update_views()
            xmlconf.save_blacklist()


    def confirm_enable_collection(self, enabled):
        d = gtk.Dialog(_("Confirm Action"), 
                None, gtk.DIALOG_MODAL,
                (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                    gtk.STOCK_OK, gtk.RESPONSE_OK))
        d.set_default_response(gtk.RESPONSE_CANCEL)

        c = self.get_current_collection()
        if enabled:
            str = _("""
    Are you sure you want to enable the \"%s\" built in collection?    
    """) % c.name
        else:
	    if c.name == "All Fonts":
		str = _("""
    Disabling the \"All Fonts\" collection is a really bad idea !

    Are you positive you want to disable the \"%s\" built in collection?    
    """) % c.name
	    elif c.name == "System":
		str = _("""  
    Disabling the \"System\" collection is a really bad idea !
    
    Are you positive you want to disable the \"%s\" built in collection?    
    """) % c.name
	    else:
		str = _("""
    Are you sure you want to disable the \"%s\" built in collection?    
        """) % c.name
        text = gtk.Label()
        text.set_text(str)
        d.vbox.pack_start(text, padding=10)
        text.show()
        ret = d.run()
        d.destroy()
        return (ret == gtk.RESPONSE_OK)

    def is_row_separator_collection(self, model, iter):
        obj = model.get(iter, 1)[0]
        return (obj is None)

    def get_current_collection(self):
        sel = collection_tv.get_selection()
        m, iter = sel.get_selected()
        if not iter:
            return
        return m.get(iter, 1)[0]
    
    def collection_changed(self, sel):
        c = self.get_current_collection()
        if c: self.show_collection(c)
        else: self.show_collection(None)

    def load_user_collections(self):
        if not exists(FM_GROUP_CONF):
            return
        doc = libxml2.parseFile(FM_GROUP_CONF)
        nodes = doc.xpathEval('//fontcollection')
        for a in nodes:
            patterns = []
            name = a.prop("name")
            xmlconf.get_fontconfig_patterns(a, patterns)
            c = Collection(name)
            c.builtin = False
            for p in patterns:
                font = g_fonts.get((p.family), None)
                if font:
                    c.fonts.append(font)
            self.add_collection(c)
            logging.info("Loaded user collection %s" % name)
        doc.freeDoc()
        check_libxml2_leak()

    def save_collection(self):
        
        # backup existing user collection in case something goes wrong
        if exists(FM_GROUP_CONF):
            if exists(FM_GROUP_CONF_BACKUP):
                os.unlink(FM_GROUP_CONF_BACKUP)
            os.rename(FM_GROUP_CONF, FM_GROUP_CONF_BACKUP)
        # disconnect the model so the user doesn't see what comes next
        collection_tv.set_model(None)
        max = 0
        # drop our default collections from the model
        while max < 4:
            path = collection_ls.get_iter(0)
            collection_ls.remove(path)
            max += 1
        # get the order of the remaining collections 
        order = []
        item = collection_ls.get_iter_first()
        while ( item != None ):
            order.append(collection_ls.get_value(item, 2))
            item = collection_ls.iter_next(item)
        # start "printing"
        doc = libxml2.newDoc("1.0")
        root = doc.newChild(None, "fontmanager", None)
        # while names in order list, match to collections list
        # get fonts attached to collection and write config
        try:
            while len(order) != 0:
                name = order[0]
                order.pop(0)
                for c in collections:
                    if c.name == name:
                        cn = root.newChild(None, "fontcollection", None)
                        cn.setProp("name", c.name)
                        for f in c.fonts:
                            p = cn.newChild(None, "pattern", None)
                            xmlconf.add_patelt_node(p, "family", f.family)
        except: 
            doc.freeDoc()
            check_libxml2_leak()
            logging.warn("There was a problem saving collection information")
            logging.info("Restoring previous collection")
            os.rename(FM_GROUP_CONF_BACKUP, FM_GROUP_CONF)
            return     
                        
        doc.saveFormatFile(FM_GROUP_CONF, format=1)
        doc.freeDoc()
        check_libxml2_leak()
        

def check_libxml2_leak():
    libxml2.cleanupParser()
    leak = libxml2.debugMemory(1)
    
    if leak > 0:
        logging.debug("libxml2 --> memory leak %s bytes" % (leak))
        libxml2.dumpMemory()
