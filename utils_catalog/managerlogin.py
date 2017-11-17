# -*- coding: utf-8 -*-
"""
/***************************************************************************
Name                 : Manager Login
Description          : Manager login(user and passwords) in server
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

from PyQt4 import QtCore, QtGui

class DialogLoginKey(QtGui.QDialog, api_server):

  def __init__(self, parent, windowTitle, icon=None):
    def initGui():
      def connect():
        buttonLogin.clicked.connect( self.onLogin )
        self.textKey.textEdited.connect( self.onTextEdited )
      #
      self.setWindowTitle( windowTitle )
      if not icon is None:
        self.setWindowIcon( icon )
      labelKey = QtGui.QLabel( "Key: ", self )
      self.labelMessage = QtGui.QLabel( self )
      self.labelMessage.hide()
      self.textKey = QtGui.QLineEdit( self )
      self.textKey.setEchoMode( QtGui.QLineEdit.Password )
      buttonLogin = QtGui.QPushButton( "Login", self )
      connect()
      layout = QtGui.QVBoxLayout( self )
      layout.addWidget( labelKey )
      layout.addWidget( self.textKey )
      layout.addWidget( buttonLogin )
      layout.addWidget( self.labelMessage )
      #
      self.resize( 4 * len( windowTitle ) + 200 , 30 )
    #
    super( DialogLoginKey, self ).__init__( parent )
    self.api = api_server
    self.response = None
    initGui()

  @QtCore.pyqtSlot( bool )
  def onLogin(self, checked):
    def setFinished(response):
      self.response = response
      loop.quit()
    
    def setKeyResponse():
      if self.response['isOk']:
        self.accept()
      else:
        self.labelMessage.setTextFormat( QtCore.Qt.RichText )
        msg = "<font color=\"red\"><b><i>Invalid key! %s</i></b></font>" % self.response['message'] 
        self.labelMessage.setText( msg )
        self.labelMessage.show()

    key = self.textKey.text().encode('ascii', 'ignore')
    self.response = None
    loop = QtCore.QEventLoop()
    self.api.setKey( key, setFinished )
    loop.exec_()
    setKeyResponse()

  @QtCore.pyqtSlot( str )
  def onTextEdited(self, text ):
    if self.labelMessage.isHidden():
      return
    self.labelMessage.hide()


class ManagerLoginKey(QtCore.QObject):
  
  def __init__(self, localSetting, api_server):
    super(ManagerLoginKey, self).__init__()
    self.localSettingKey = "{}/key".format( localSetting ) # ~/.config/QGIS/QGIS2.conf
    self.api = api_server
  
  def dialogLogin(self, dataDlg, dataMsgBox, setResult):

    def saveKeyDlg():
      arg = ( dlg, dataMsgBox['title'], dataMsgBox['msg'], QtGui.QMessageBox.Yes | QtGui.QMessageBox.No )
      reply = QtGui.QMessageBox.question( *arg ) 
      if reply == QtGui.QMessageBox.Yes:
        s = QtCore.QSettings()
        s.setValue( self.localSettingKey, self.api.validKey )
    
    @QtCore.pyqtSlot( int )
    def finished(result):
      isOk = result == QtGui.QDialog.Accepted 
      if isOk:
        saveKeyDlg()
      setResult( isOk )

    arg = ( dataDlg['parent'] , dataDlg['windowTitle'], dataDlg['icon'], self.api )
    dlg = DialogLoginKey( *arg )
    dlg.finished.connect( finished )
    dlg.exec_()
    
  def getKeySetting(self):
    s = QtCore.QSettings()
    return s.value( self.localSettingKey, None )
  
  def removeKey(self):
    s = QtCore.QSettings()
    s.remove( self.localSettingKey )
