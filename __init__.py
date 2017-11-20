# -*- coding: utf-8 -*-
"""
/***************************************************************************
Name                 : Catalog Remote Pixel
Description          : Create catalog from Remote Pixel
Date                 : November, 2017
copyright            : (C) 2017 by Luiz Motta
email                : motta.luiz@gmail.com

 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

import os
from PyQt4 import QtGui

from catalogrp import CatalogRP
from utils_catalog.catalogplugin import CatalogPlugin

def classFactory(iface):
    return CatalogRPPlugin( iface )

class CatalogRPPlugin(CatalogPlugin):
    def __init__(self, iface):
        arg = ( iface, u"&Catalog Remote Pixel", 'Catalog Remote Pixel' )
        CatalogPlugin.__init__(self, *arg )
        self.icon = QtGui.QIcon( os.path.join( os.path.dirname(__file__), 'catalogrp.svg' ) )
        self.ctl = CatalogRP( iface.mainWindow(), self.icon )
