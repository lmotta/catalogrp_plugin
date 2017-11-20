# -*- coding: utf-8 -*-
"""
/***************************************************************************
Name                 : Catalog Plugin
Description          : Base Class for Catalog Plugins
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

from apiqtcatalog import API_Catalog


class CatalogPlugin(object):
    def __init__(self, iface, name, pluginName ):
        self.iface = iface
        self.name = name
        self.pluginName = pluginName
        API_Catalog.copyExpression()
        # Set By Derivated Class
        self.icon, self.ctl = None, None

    def initGui(self):
        dataActions = [
            {
                'isSepatator': False,
                'name': self.name,
                'icon': self.icon,
                'method': self.run
            },
            {
                'isSepatator': False,
                'name': 'Setting...',
                'icon': QgsCore.QgsApplication.getThemeIcon('/mActionOptions.svg'),
                'method': self.config
            },
            { 'isSepatator': True },             
            {
              'isSepatator': False,
              'name': 'Copy register to Clipboard',
              'icon': QgsCore.QgsApplication.getThemeIcon('/mActionOptions.svg'),
              'method': self.clipboardRegister
            },
            {
              'isSepatator': False,
              'name': 'Clear register',
              'icon': QgsCore.QgsApplication.getThemeIcon('/mActionOptions.svg'),
              'method': self.clearRegister
            }
        ]
        mw = self.iface.mainWindow()
        popupMenu = QtGui.QMenu( mw )
        for d in dataActions:
          if d['isSepatator']:
            a = QtGui.QAction( mw )
            a.setSeparator(True)
          else:
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

    @QtCore.pyqtSlot()
    def clearRegister(self):
      self.ctl.clearRegister()
  
    @QtCore.pyqtSlot()
    def clipboardRegister(self):
      self.ctl.clipboardRegister()
