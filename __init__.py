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

from PyQt4 import QtCore, QtGui
from qgis import core as QgsCore, gui as QgsGui

from catalogrp import CatalogRP, API_Catalog

def classFactory(iface):
    return CatalogRPPlugin( iface )

class CatalogRPPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.name = u"&Catalog Remote Pixel"
        self.pluginName = "Catalog Remote Pixel"
        self.icon = QtGui.QIcon( os.path.join( os.path.dirname(__file__), 'catalogrp.svg' ) )
        self.msgBar = iface.messageBar()
        self.ctl = CatalogRP( self.icon )
        API_Catalog.copyExpression()
    
    def initGui(self):
        dataActions = [
            {
                'name': 'Catalog Remote Pixel',
                'icon': QtGui.QIcon( self.icon ),
                'method': self.run
            },
            {
                'name': 'Setting...',
                'icon': QgsCore.QgsApplication.getThemeIcon('/mActionOptions.svg'),
                'method': self.config
            }
        ]
        
        mw = self.iface.mainWindow()
        popupMenu = QtGui.QMenu( mw )
        for d in dataActions:
            a = QtGui.QAction( d['icon'], d['name'], mw )
            a.triggered.connect( d['method'] )
            self.iface.addPluginToRasterMenu( self.name, a )
            popupMenu.addAction(  a )
        defaultAction = popupMenu.actions()[0]
        self.toolButton = QtGui.QToolButton()
        self.toolButton.setPopupMode( QtGui.QToolButton.MenuButtonPopup )
        self.toolButton.setMenu( popupMenu )
        self.toolButton.setDefaultAction( defaultAction )
        
        self.actionPopupMenu = self.iface.addToolBarWidget( self.toolButton )
        self.ctl.enableRun.connect( self.actionPopupMenu.setEnabled )

    def unload(self):
        self.iface.removeToolBarIcon( self.actionPopupMenu )
        for a in self.toolButton.menu().actions():
          self.iface.removePluginRasterMenu( self.name, a )
          del a
        del self.actionPopupMenu
        del self.ctl
  
    @QtCore.pyqtSlot()
    def run(self):
        if self.iface.mapCanvas().layerCount() == 0:
          msg = "Need layer(s) in map"
          self.iface.messageBar().pushMessage( self.pluginName, msg, QgsGui.QgsMessageBar.WARNING, 2 )
          return

        if not self.ctl.isHostLive:
          self.ctl.hostLive()
          if not self.ctl.isHostLive:
              return

        self.ctl.createLayerScenes()

    @QtCore.pyqtSlot()
    def config(self):
        self.ctl.settingImages()
