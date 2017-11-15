# -*- coding: utf-8 -*-
"""
/***************************************************************************
Name                 : Qt API for Catalog
Description          : Abstract Class for Catalog API
Date                 : November, 2017
copyright            : (C) 2018 by Luiz Motta
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

import json, datetime, os

from PyQt4 import QtCore, QtGui, QtNetwork


class AccessSite(QtCore.QObject):

  # Signals
  finished = QtCore.pyqtSignal( dict)
  send_data = QtCore.pyqtSignal(QtCore.QByteArray)
  status_download = QtCore.pyqtSignal(int, int)
  status_erros = QtCore.pyqtSignal(list)
  
  ErrorCodeAttribute = { 
     10: 'Canceled request',
    400: 'Bad request syntax',
    401: 'Unauthorized',
    402: 'Payment required',
    403: 'Forbidden',
    404: 'Not found',
    500: 'Internal error',
    501: 'Not implemented',
    502: 'Bad Gateway'  
  }

  def __init__(self):
    super( AccessSite, self ).__init__()
    self.networkAccess = QtNetwork.QNetworkAccessManager(self)
    self.totalReady = self.reply = self.triedAuthentication = self.isKilled = None
    # Input by self.run
    self.credential = self.responseAllFinished = None

  def run(self, url, credential=None, responseAllFinished=True, json_request=None):
    if credential is None:
      credential = {'user': '', 'password': ''}
    ( self.credential, self.responseAllFinished ) = ( credential, responseAllFinished )
    self._connect()
    self.totalReady = 0
    self.isKilled = False
    request = QtNetwork.QNetworkRequest( url )
    if json_request is None:
      reply = self.networkAccess.get( request )
    else:
      request.setHeader( QtNetwork.QNetworkRequest.ContentTypeHeader, "application/json" )
      data = QtCore.QByteArray( json.dumps( json_request ) )
      reply = self.networkAccess.post( request, data )
    if reply is None:
      response = { 'isOk': False, 'message': "Network error", 'errorCode': -1 }
      self._connect( False )
      self.finished.emit( response )
      return

    self.triedAuthentication = False
    self.reply = reply
    self._connectReply()
  
  def kill(self):
    self.isKilled = True
  
  def isRunning(self):
    return ( not self.reply is None and self.reply.isRunning() )  

  def _connect(self, isConnect=True):
    ss = [
      { 'signal': self.networkAccess.finished, 'slot': self.replyFinished },
      { 'signal': self.networkAccess.authenticationRequired, 'slot': self.authenticationRequired }
    ]
    if isConnect:
      for item in ss:
        item['signal'].connect( item['slot'] )  
    else:
      for item in ss:
        item['signal'].disconnect( item['slot'] )

  def _connectReply(self, isConnect=True):
    ss = [
      { 'signal': self.reply.readyRead, 'slot': self.readyRead },
      { 'signal': self.reply.downloadProgress, 'slot': self.downloadProgress },
      { 'signal': self.reply.sslErrors, 'slot': self.sslErrors }
    ]
    if isConnect:
      for item in ss:
        item['signal'].connect( item['slot'] )  
    else:
      for item in ss:
        item['signal'].disconnect( item['slot'] )

  def _clearConnect(self):
    self._connect( False ) # self.reply.close() -> emit signal self.networkAccess.finished
    self._connectReply( False )
    self.reply.close()
    self.reply.deleteLater();
    del self.reply
    self.reply = None

  def _redirectionReply(self, url):
    self._clearConnect()
    self._connect()
    if url.isRelative():
      url = url.resolved( url )

    request = QtNetwork.QNetworkRequest( url )
    reply = self.networkAccess.get( request )
    if reply is None:
      response = { 'isOk': False, 'message': "Netwok error", 'errorCode': -1 }
      self._connect( False )
      self.finished.emit( response )
      return

    self.reply = reply
    self._connectReply()
    
  def _errorCodeAttribute(self, code):
    msg = 'Error network' if not code in self.ErrorCodeAttribute.keys() else AccessSite.ErrorCodeAttribute[ code ]
    response = { 'isOk': False, 'message': msg, 'errorCode': code }
    self._clearConnect()
    self.finished.emit( response )

  @QtCore.pyqtSlot(QtNetwork.QNetworkReply)
  def replyFinished(self, reply) :
    if self.isKilled:
      self._errorCodeAttribute(10)

    if reply.error() != QtNetwork.QNetworkReply.NoError :
      response = { 'isOk': False, 'message': reply.errorString(), 'errorCode': reply.error() }
      self._clearConnect()
      self.finished.emit( response )
      return

    urlRedir = reply.attribute( QtNetwork.QNetworkRequest.RedirectionTargetAttribute )
    if not urlRedir is None and urlRedir != reply.url():
      self._redirectionReply( urlRedir )
      return

    codeAttribute = reply.attribute( QtNetwork.QNetworkRequest.HttpStatusCodeAttribute )
    if codeAttribute != 200:
      self._errorCodeAttribute( codeAttribute )
      return

    statusRequest = {
      'contentTypeHeader': reply.header( QtNetwork.QNetworkRequest.ContentTypeHeader ),
      'lastModifiedHeader': reply.header( QtNetwork.QNetworkRequest.LastModifiedHeader ),
      'contentLengthHeader': reply.header( QtNetwork.QNetworkRequest.ContentLengthHeader ),
      'statusCodeAttribute': reply.attribute( QtNetwork.QNetworkRequest.HttpStatusCodeAttribute ),
      'reasonPhraseAttribute': reply.attribute( QtNetwork.QNetworkRequest.HttpReasonPhraseAttribute )
    }
    response = { 'isOk': True, 'statusRequest': statusRequest }
    if self.responseAllFinished:
      response[ 'data' ] = reply.readAll()
    else:
      response[ 'totalReady' ] = self.totalReady

    self._clearConnect()
    self.finished.emit( response )

  @QtCore.pyqtSlot(QtNetwork.QNetworkReply, QtNetwork.QAuthenticator)
  def authenticationRequired (self, reply, authenticator):
    if not self.triedAuthentication: 
      authenticator.setUser( self.credential['user'] ) 
      authenticator.setPassword( self.credential['password'] )
      self.triedAuthentication = True
    else:
      self._errorCodeAttribute( 401 )

  @QtCore.pyqtSlot()
  def readyRead(self):
    if self.isKilled:
      self._errorCodeAttribute(10)
      return

    if self.responseAllFinished:
      return

    urlRedir = self.reply.attribute( QtNetwork.QNetworkRequest.RedirectionTargetAttribute )
    if not urlRedir is None and urlRedir != self.reply.url():
      self._redirectionReply( urlRedir )
      return

    codeAttribute = self.reply.attribute( QtNetwork.QNetworkRequest.HttpStatusCodeAttribute )
    if codeAttribute != 200:
      self._errorCodeAttribute( codeAttribute )
      return

    data = self.reply.readAll()
    if data is None:
      return
    self.totalReady += len ( data )
    self.send_data.emit( data )

  @QtCore.pyqtSlot(int, int)
  def downloadProgress(self, bytesReceived, bytesTotal):
    if self.isKilled:
      self._errorCodeAttribute(10)
    else:
      self.status_download.emit( bytesReceived, bytesTotal )

  @QtCore.pyqtSlot( list )
  def sslErrors(self, errors):
    lstErros = map( lambda e: e.errorString(), errors )
    self.status_erros.emit( lstErros )
    self.reply.ignoreSslErrors()


class ValueErrorSatellite(ValueError):
  def __init__(self, satellite, satellites):
    msg = "Catalog: Invalid '{}'. Values are {}".format( satellite, ','.join( satellites ) )
    self.strerror = msg
    self.args = { msg }


class API_Catalog(QtCore.QObject):
  expressionFile = 'catalog_expressions.py'
  expressionDir = 'expressions'
  def __init__(self, credential=None):
    super( API_Catalog, self ).__init__()
    self.credential = credential
    self.access = AccessSite()
    self.currentUrl = None

  def _clearResponse(self, response):
    if response.has_key('data'):
      response['data'].clear()
      del response[ 'data' ]
    del response[ 'statusRequest' ]

  def kill(self):
    self.access.kill()

  def isKilled(self):
    return self.access.isKilled

  def isRunning(self):
    return self.access.isRunning()

  def isHostLive(self, setFinished):
    @QtCore.pyqtSlot(dict)
    def finished( response):
      self.access.finished.disconnect( finished )
      if response['isOk']:
        response[ 'isHostLive' ] = True
        self._clearResponse( response )
      else:
        if response['errorCode'] == QtNetwork.QNetworkReply.HostNotFoundError:
          response[ 'isHostLive' ] = False
          response[ 'message' ] += "\nURL = %s" % self.currentUrl
        else:
          response[ 'isHostLive' ] = True

      setFinished( response )

    self.access.finished.connect( finished )
    self.access.run( self.currentUrl, self.credential )

  def requestForJson(self, url, setFinished):
    @QtCore.pyqtSlot(dict)
    def finished( response):
      self.access.finished.disconnect( finished )
      if response[ 'isOk' ]:
        isJson = response['statusRequest']['contentTypeHeader'] == 'application/json'
        response['isJSON'] = isJson
        if isJson:
          data = json.loads( str( response['data'] ) )
          response['results'] = data['results']
          response['meta_found'] = data['meta']['found']
          del data['meta']
        
        self._clearResponse( response )

      setFinished( response )

    self.access.finished.connect( finished )
    self.access.run( QtCore.QUrl( url ), self.credential )

  @staticmethod
  def getValue(jsonMetadataFeature, keys):
    dicMetadata = jsonMetadataFeature
    if not isinstance( jsonMetadataFeature, dict):
      dicMetadata = json.loads( jsonMetadataFeature )
    msgError = None
    e_keys = map( lambda item: "'%s'" % item, keys )
    try:
      value = reduce( lambda d, k: d[ k ], [ dicMetadata ] + keys )
    except KeyError as e:
      msgError = "Catalog: Have invalid key: {}".format( ' -> '.join( e_keys) )
    except TypeError as e:
      msgError = "Catalog: The last key is invalid: {}".format( ' -> '.join( e_keys) )

    if msgError is None and isinstance( value, dict):
      msgError = "Catalog: Missing key: {}".format( ' -> '.join( e_keys) )

    return ( True, value ) if msgError is None else ( False, msgError ) 

  @staticmethod
  def getTextTreeMetadata( jsonMetadataFeature ):
    def fill_item(strLevel, value):
      if not isinstance( value, ( dict, list ) ):
        items[-1] += ": %s" % value
        return

      if isinstance( value, dict ):
        for key, val in sorted( value.iteritems() ):
          items.append( "%s%s" % ( strLevel, key ) )
          strLevel += signalLevel
          fill_item( strLevel, val )
          strLevel = strLevel[ : -1 * len( signalLevel ) ]
      return

      if isinstance( value, list ):
        for val in value:
          if not isinstance( value, ( dict, list ) ):
            items[-1] += ": %s" % value
          else:
            text = '[dict]' if isinstance( value, dict ) else '[list]'
            items.append( "%s%s" % ( strLevel, text ) )
            strLevel += signalLevel
            fill_item( strLevel, val )
            strLevel = strLevel[ : -1 * len( signalLevel ) ]

    signalLevel = "- "
    items = []
    fill_item( '', json.loads( jsonMetadataFeature ) )
    
    return '\n'.join( items )

  @staticmethod
  def getHtmlTreeMetadata(value, html):
    if isinstance( value, dict ):
      html += "<ul>"
      for key, val in sorted( value.iteritems() ):
        if not isinstance( val, dict ):
          html += "<li>%s: %s</li> " % ( key, val )
        else:
          html += "<li>%s</li> " % key
        html = API_Catalog.getHtmlTreeMetadata( val, html )
      html += "</ul>"
      return html
    return html

  @staticmethod
  def getTextValuesMetadata( dicMetadataFeature ):
    def fill_item(value):
      def addValue(_value):
        _text = "'%s' = %s" % (", ".join( keys ),  _value )
        items.append( _text )

      if not isinstance( value, ( dict, list ) ):
        addValue( value )
        return

      if isinstance( value, dict ):
        for key, val in sorted( value.iteritems() ):
          keys.append( '"%s"' % key )
          fill_item( val )
          del keys[ -1 ]
      return

      if isinstance( value, list ):
        for val in value:
          if not isinstance( val, ( dict, list ) ):
            addValue( val )
          else:
            text = "[dict]" if isinstance( val, dict ) else "[list]"
            keys.append( '"%s"' % text )
            fill_item( val )
            del keys[ -1 ]

    keys = []
    items = []
    fill_item( dicMetadataFeature )
    
    return '\n'.join( items )

  @staticmethod
  def getQTreeWidgetMetadata( jsonMetadataFeature, parent=None ):
    def createTreeWidget():
      tw = QTreeWidget(parent)
      tw.setColumnCount( 2 )
      tw.header().hide()
      tw.clear()
      return tw
 
    def fill_item(item, value):
      item.setExpanded( True )
      if not isinstance( value, ( dict, list ) ):
        item.setData( 1, QtCore.Qt.DisplayRole, value )
        return

      if isinstance( value, dict ):
        for key, val in sorted( value.iteritems() ):
          child = QTreeWidgetItem()
          child.setText( 0, unicode(key) )
          item.addChild( child )
          fill_item( child, val )
      return

      if isinstance( value, list ):
        for val in value:
          if not isinstance( val, ( dict, list ) ):
            item.setData( 1, QtCore.Qt.DisplayRole, val )
          else:
            child = QTreeWidgetItem()
            item.addChild( child )
            text = '[dict]' if isinstance( value, dict ) else '[list]'
            child.setText( 0, text )
            fill_item( child , val )

          child.setExpanded(True)

    tw = createTreeWidget()
    fill_item( tw.invisibleRootItem(), json.loads( jsonMetadataFeature ) )
    tw.resizeColumnToContents( 0 )
    tw.resizeColumnToContents( 1 )
    
    return tw

  @staticmethod
  def copyExpression():
    dirname = os.path.dirname
    fromExp = os.path.join( dirname( __file__ ), API_Catalog.expressionFile )
    dirExp = os.path.join( dirname( dirname( dirname( __file__ ) ) ), API_Catalog.expressionDir )
    toExp = os.path.join( dirExp , API_Catalog.expressionFile )
    if os.path.isdir( dirExp ):
      if QtCore.QFile.exists( toExp ):
        QtCore.QFile.remove( toExp ) 
      QtCore.QFile.copy( fromExp, toExp ) 
