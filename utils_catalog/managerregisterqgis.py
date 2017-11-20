# -*- coding: utf-8 -*-
"""
/***************************************************************************
Name                 : Manager Login Key
Description          : Manager Key in server
Date                 : November, 2017
copyright            : (C) 2015 by Luiz Motta
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

from PyQt4 import QtCore, QtGui


class DialogRegister(QtGui.QDialog):

  def __init__(self, parent, title, icon, apiServer):
    def initGui():
      def getLineEditKeys():
        editKeys = {}
        for k in sorted( apiServer.keysSetting.keys() ):
          v = apiServer.keysSetting[ k ]
          l = QtGui.QHBoxLayout( self )
          label = QtGui.QLabel( "{}:".format( v['label'] ), self )
          l.addWidget( label )
          editKeys[ k ] = QtGui.QLineEdit( self )
          if v['isPassword']:
            editKeys[ k ].setEchoMode( QtGui.QLineEdit.Password )
          l.addWidget( editKeys[ k ] )
          layoutMain.addLayout( l )

        return editKeys
        
      def connect():
        buttonLogin.clicked.connect( self.onLogin )
        for edit in self.editKeys.values():
          edit.textEdited.connect( self.onTextEdited )

      self.setWindowTitle( title )
      if not icon is None:
        self.setWindowIcon( icon )
      layoutMain = QtGui.QVBoxLayout( self )
      self.editKeys = getLineEditKeys()
      self.labelError = QtGui.QLabel( self )
      self.labelError.hide()
      layoutMain.addWidget( self.labelError )
      buttonLogin = QtGui.QPushButton( "Login", self )
      layoutMain.addWidget( buttonLogin )
      self.setLayout( layoutMain )
      connect()
      #
      self.resize( 4 * len( title ) + 200 , 30 )
    #
    super( DialogRegister, self ).__init__( parent )
    self.apiServer = apiServer 
    self.response = None
    initGui()

  def getUrlKeys(self):
    urlKeys = {}
    for k, v in self.editKeys.iteritems():
      urlKeys[ k ] = v.text().encode('ascii', 'ignore')
    return urlKeys

  @QtCore.pyqtSlot( bool )
  def onLogin(self, checked):
    def setFinished(response):
      self.response = response

    def setKeyResponse():
      if self.response['isOk']:
        self.accept()
      else:
        self.labelError.setTextFormat( QtCore.Qt.RichText )
        msg = "<font color=\"red\"><b><i>{}</i></b></font>"
        msg = msg.format( self.response['message'] ) 
        self.labelError.setText( msg )
        self.labelError.show()

    urlKeys = self.getUrlKeys()
    self.response = None
    self.apiServer.setKeys( urlKeys, setFinished )
    setKeyResponse()

  @QtCore.pyqtSlot( str )
  def onTextEdited(self, text ):
    if self.labelError.isHidden():
      return
    self.labelError.hide()


class ManagerRegisterQGis(QtCore.QObject):
  
  def __init__(self, localSetting, apiServer):
    super(ManagerRegisterQGis, self).__init__()
    self.apiServer = apiServer
    self.localSetting = localSetting # ~/.config/QGIS/QGIS2.conf
    self.isOkRegister = False

  def _getLocalSettingKeys(self):
    localSettingKeys = {} 
    for k in self.apiServer.keysSetting:
      localSettingKeys[ k ] = "{}/{}".format( self.localSetting, k )
    return localSettingKeys

  def dialogRegister(self, title, parent, icon):

    def saveKeyDlg():
      msg = "Do you like save register(QGIS setting)?"
      reply = QtGui.QMessageBox.question( dlg, title, msg, QtGui.QMessageBox.Yes | QtGui.QMessageBox.No) 
      if reply == QtGui.QMessageBox.Yes:
        localSettingKeys = self._getLocalSettingKeys()
        urlKeys = dlg.getUrlKeys()
        s = QtCore.QSettings()
        for k in urlKeys.keys():
          s.setValue( localSettingKeys[ k ], urlKeys[ k ] )

    @QtCore.pyqtSlot( int )
    def finished(result):
      isOk = result == QtGui.QDialog.Accepted 
      if isOk:
        self.isOkRegister = True
        saveKeyDlg()

    self.isOkRegister = False
    dlg = DialogRegister( parent, title, icon, self.apiServer )
    dlg.finished.connect( finished )
    dlg.exec_()
    
  def get(self):
    localSettingKeys = self._getLocalSettingKeys()
    s = QtCore.QSettings()
    registers = {}
    for k, v in localSettingKeys.iteritems():
      registers[ k ] = s.value( v, None )
    return registers

  def remove(self):
    localSettingKeys = self._getLocalSettingKeys()
    s = QtCore.QSettings()
    for v in localSettingKeys.values():
      s.remove( v )

"""
API_RP.setKey(urlKeys, setFinished)
urlKeys = { 
  'landsat-8': 'mn2iekg7k7',
  'sentinel-2': 'jmcka7torb'
}
"""