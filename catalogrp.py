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

import os, json

from PyQt4 import QtCore, QtGui
from qgis import core as QgsCore, gui as QgsGui, utils as QgsUtils

from apiqtcatalog import API_Catalog
from legendlayercatalog import ( DialogCatalogSetting, LegendCatalogLayer )
from legendlayerraster import LegendRasterGeom
from messagebarcancel import MessageBarCancel, MessageBarCancelProgress
from workertms import WorkerCreateTMS_GDAL_WMS 


class API_RP(API_Catalog):
  def __init__(self):
    self.satellites = ['landsat-8', 'sentinel-2']    
    l_url = [
      'https://api.developmentseed.org/satellites/?limit=200',
      'satellite_name={satellite}',
      'date_from={date_from}', 'date_to={date_to}',
      'intersects={geom}'
    ]
    self.urlSearch = '&'.join( l_url )
    self.urlImages = {
        'landsat-8': "https://mn2iekg7k7.execute-api.us-west-2.amazonaws.com/production/landsat",
        'sentinel-2': "https://jmcka7torb.execute-api.eu-central-1.amazonaws.com/production/sentinel"
    }
    #
    API_RP.title = 'Catalog Remote Pixel'
    super( API_RP, self ).__init__()
  
  def isHostLive(self, setFinished):
    self.currentUrl = QtCore.QUrl( self.urlImages['landsat-8'] )
    super( API_RP, self ).isHostLive( setFinished )

  def getScenes(self, satellite, jsonGeom, date_from, date_to, setFinished):
    """
    Get Json metadata from server.
    Params:
      satellite:   Name of satellite
      jsonGeom:    Geojson of Geometry { 'type': 'Polygon', 'coordinates': [...] }
      dateFrom:    Start date (AAA-mm-DD)
      dateTo:      End date(AAA-mm-DD)
      setFinished: Method to send response
    """
    if not satellite in self.satellites:
      raise ValueErrorSatellite( satellite, self.satellites )

    url = self.urlSearch.format( satellite=satellite, date_from=date_from, date_to=date_to, geom=json.dumps( jsonGeom ) )
    url = QtCore.QUrl( url )
    super( API_RP, self ).getScenes( url, setFinished)

  def getURL_TMS(self, feat, sbands):
    ( isOk, satellite) = API_RP.getValue( feat['meta_json'], ['satellite_name'] )
    ( isOk, product_id) = API_RP.getValue( feat['meta_json'], ['product_id'] )
    rgb = ','.join( sbands)
    if satellite == 'landsat-8':
      rgb = rgb.replace('B', '')
    url = "{url}/tiles/{{product_id}}/{{xyz}}.png?rgb={{rgb}}&tile=256&pan=true".format( url=self.urlImages[ satellite ] )
    url = url.format( product_id=product_id, xyz='{z}/{x}/{y}',rgb=rgb)
    return url


class DialogCatalogSettingRP(DialogCatalogSetting):
  configQGIS = 'catalogrp_plugin' # ~/.config/QGIS/QGIS2.conf
  def __init__(self, parent, icon, dataSetting):
    bandsLandsat1_5  =  [ "B{:d}".format(n)   for n in xrange(1,6) ]
    bandsSentinel2_8 =  [ "B{:02d}".format(n) for n in xrange(2,9) ]
    satellites = {
      'landsat-8':  { 'dates': 'Since 2013',  'bands': bandsLandsat1_5 + ['B6','B7','B9'] },
      'sentinel-2': { 'dates': 'Since 2015',  'bands': bandsSentinel2_8 + ['B8A','B11','B12'] }
    }
    #
    arg = ( parent, icon, dataSetting, satellites, DialogCatalogSettingRP.configQGIS, DialogCatalogSettingRP.getVegetationBands )
    super( DialogCatalogSettingRP, self ).__init__( *arg )

  @staticmethod
  def getVegetationBands(satellite):
    if satellite == 'landsat-8':
      return ['B6', 'B5', 'B4']
    else: # sentinel2
      return ['B11', 'B8A', 'B04']
    

class CatalogRP(QtCore.QObject):

  pluginName = u'Catalog Remote Pixel'
  styleFile = 'rp_scenes.qml'
  expressionFile = 'rp_expressions.py'
  expressionDir = 'expressions'

  enableRun = QtCore.pyqtSignal( bool )
  
  def __init__(self, icon):
    super(CatalogRP, self).__init__()
    self.catalogName = "Remote Pixel"
    self.canvas = QgsUtils.iface.mapCanvas()
    self.msgBar = QgsUtils.iface.messageBar()
    self.logMessage = QgsCore.QgsMessageLog.instance().logMessage
    self.icon = icon
    self.mainWindow = QgsUtils.iface.mainWindow()

    self.apiServer = API_RP()
    self.legendRasterGeom = LegendRasterGeom( CatalogRP.pluginName )
    self.thread = self.worker = None # initThread
    self.mbcancel = None # Need for worker
    self.isHostLive = False

    self.layer = None
    self.hasCriticalMessage = None
    self.scenesResponse, self.scenesFound = None, None
    self.messageProcess = self.isOkProcess = None
    self.currentItem, self.stepProcessing = None, None
    self.catalog = { 'ltg': None, 'satellite': None }

    arg = ( CatalogRP.pluginName, self.CreateTMS_GDAL_WMS )
    self.legendCatalogLayer = LegendCatalogLayer( *arg )
    
    self.settings = DialogCatalogSettingRP.getSettings( DialogCatalogSettingRP.configQGIS )
    self.settings['satellite'] = 'landsat-8'
    self.settings['rgb'] = DialogCatalogSettingRP.getVegetationBands( self.settings['satellite'] )

    self._connect()
    self._initThread()

  def __del__(self):
    self._connect( False )
    self._finishThread()
    del self.legendRasterGeom

  def _initThread(self):
    self.thread = QtCore.QThread( self )
    self.thread.setObjectName( "QGIS_Plugin_Catalog_RP" )
    self.worker = WorkerCreateTMS_GDAL_WMS( self.logMessage, self.legendRasterGeom )
    self.worker.moveToThread( self.thread )
    self.thread.started.connect( self.worker.run )

  def _finishThread(self):
    self.thread.started.disconnect( self.worker.run )
    self.worker.deleteLater()
    self.thread.wait()
    self.thread.deleteLater()
    del self.worker
    self.thread = self.worker = None

  def _connect(self, isConnect = True):
    s = { 'signal': QgsCore.QgsMapLayerRegistry.instance().layerWillBeRemoved, 'slot': self.layerWillBeRemoved }
    if isConnect:
      s['signal'].connect( s['slot'] )
    else:
      s['signal'].disconnect( s['slot'] )

  def _startProcess(self, funcKill, hasProgressFile=False):
    def getFeatureIteratorTotal():
      hasSelected = True
      iter = self.layer.selectedFeaturesIterator()
      total = self.layer.selectedFeatureCount()
      if total == 0:
        hasSelected = False
        iter = self.layer.getFeatures()
        total = self.layer.featureCount()

      return ( iter, total, hasSelected )

    ( iterFeat, totalFeat, hasSelected ) = getFeatureIteratorTotal()
    if totalFeat == 0:
      msg = "Not have images for processing."
      arg = ( CatalogRP.pluginName, msg, QgsGui.QgsMessageBar.WARNING, 4 ) 
      self.msgBar.pushMessage( *arg )
      return { 'isOk': False }

    msg = "selected" if hasSelected else "all"
    msg = "Processing {0} images({1})...".format( totalFeat, msg )
    arg = ( CatalogRP.pluginName, self.msgBar, msg, totalFeat, funcKill, hasProgressFile )
    self.mbcancel = MessageBarCancelProgress( *arg )
    self.enableRun.emit( False )
    self.legendCatalogLayer.enabledProcessing( False )
    return { 'isOk': True, 'iterFeat': iterFeat }

  def _endProcessing(self, nameProcessing, totalError):
    self.enableRun.emit( True )
    if self.layer is None:
      self.msgBar.popWidget()
      return
    
    self.legendCatalogLayer.enabledProcessing()
    
    self.msgBar.popWidget()
    if not self.mbcancel.isCancel and totalError > 0:
      msg = "Has error in download (total = {0}) - See log messages".format( totalError )
      arg = ( CatalogRP.pluginName, msg, QgsGui.QgsMessageBar.CRITICAL, 4 )
      self.msgBar.pushMessage( *arg )
      return

    if self.mbcancel.isCancel:
      f_msg = "Canceled '{0}' by user"
      typMessage = QgsGui.QgsMessageBar.WARNING
    else:
      f_msg = "Finished '{0}'"
      typMessage = QgsGui.QgsMessageBar.INFO
    
    msg = f_msg.format( nameProcessing )
    self.msgBar.clearWidgets()
    self.msgBar.pushMessage( self.pluginName, msg, typMessage, 4 )

  def hostLive(self):
    def setFinished(response):
      self.isOkProcess = response[ 'isHostLive' ]
      if not self.isOkProcess:
        self.messageProcess = response[ 'message' ]
      loop.quit()

    loop = QtCore.QEventLoop()
    msg = "Checking server..."
    self.msgBar.pushMessage( self.pluginName, msg, QgsGui.QgsMessageBar.INFO )
    self.enableRun.emit( False )
    self.apiServer.isHostLive( setFinished )
    loop.exec_()
    self.msgBar.popWidget()
    if not self.isOkProcess:
      self.msgBar.pushMessage( self.pluginName, self.messageProcess, QgsGui.QgsMessageBar.CRITICAL, 4 )
      self.messageProcess = None
    self.isHostLive = self.isOkProcess
    self.enableRun.emit( True )

  def createLayerScenes(self):
    def hasSettingPath():
      # self.settings setting by __init__.setSearchSettings()
      if self.settings['path'] == DialogCatalogSettingRP.titleSelectDirectory:
        msg = "Please, {0}".format( DialogCatalogSettingRP.titleSelectDirectory )
        self.msgBar.pushMessage( CatalogRP.pluginName, msg, QgsGui.QgsMessageBar.WARNING, 6 )
        return False
      return True

    def createLayer():
      atts = [
        "id:string(25)", "acquired:string(35)", "thumbnail:string(2000)",
        "meta_html:string(2000)", "meta_json:string(2000)",
        "meta_jsize:integer"
      ]
      l_fields = map( lambda item: "field=%s" % item, atts  )
      l_fields.insert( 0, "Multipolygon?crs=epsg:4326" )
      l_fields.append( "index=yes" )
      uri = '&'.join( l_fields )
      
      date1 = self.settings['date1'].toString( QtCore.Qt.ISODate )
      date2 = self.settings['date2'].toString( QtCore.Qt.ISODate )
      name = "{} {}({} to {})".format( self.catalogName,self.settings['satellite'], date1, date2)
      vl = QgsCore.QgsVectorLayer( uri, name, "memory" )
      # Add layer
      self.layer = QgsCore.QgsMapLayerRegistry.instance().addMapLayer( vl, addToLegend=False )
      layerTree = QgsCore.QgsProject.instance().layerTreeRoot().insertLayer( 0, self.layer )
      # Symbology
      ns = os.path.join( os.path.dirname( __file__ ), CatalogRP.styleFile )
      self.layer.loadNamedStyle( ns )
      QgsUtils.iface.legendInterface().refreshLayerSymbology( self.layer )
      layerTree.setVisible( QtCore.Qt.Unchecked )

    def removeFeatures():
      prov = self.layer.dataProvider()
      if prov.featureCount() > 0:
        self.layer.startEditing()
        prov.deleteFeatures( self.layer.allFeatureIds() )
        self.layer.commitChanges()
        self.layer.updateExtents()

    def populateLayer():
      def requestScenes(satellite, date1, date2, geojson):
        def setFinished(response):
          self.isOkProcess = response['isOk']
          if self.isOkProcess:
            self.scenesResponse = response['results']
            self.scenesFound = response[ 'meta_found' ]
          else:
            self.messageProcess = response[ 'message' ]
          loop.quit()

        loop = QtCore.QEventLoop()
        self.apiServer.getScenes( satellite, geojson, date1, date2, setFinished )
        loop.exec_()
        if not self.isOkProcess: 
          self.hasCriticalMessage = True
          self.msgBar.popWidget()
          self.msgBar.pushMessage( CatalogRP.pluginName, self.messageProcess, QgsGui.QgsMessageBar.CRITICAL, 4 )
          self.messageProcess = None
          self.scenesResponse = None

      def getFeature(itemResponse, fields):
        # Fields
        # 'id', 'acquired', 'thumbnail', 'meta_html', 'meta_json', 'meta_jsize'
        vFields =  { }
        pairkeys = { 'id': 'scene_id', 'acquired': 'date', 'thumbnail': 'thumbnail' }
        for k, v in pairkeys.items():
          vFields[ k ] = itemResponse[ v ]
        del itemResponse['thumbnail']
        # Geom
        geom = None
        geomItem = itemResponse['data_geometry']
        geomCoords = geomItem['coordinates']
        if geomItem['type'] == 'Polygon':
          qpolygon = map ( lambda polyline: map( lambda item: QgsCore.QgsPoint( item[0], item[1] ), polyline ), geomCoords )
          geom = QgsCore.QgsGeometry.fromMultiPolygon( [ qpolygon ] )
        elif geomItem['type'] == 'MultiPolygon':
          qmultipolygon = []
          for polygon in geomCoords:
              qpolygon = map ( lambda polyline: map( lambda item: QgsCore.QgsPoint( item[0], item[1] ), polyline ), polygon )
              qmultipolygon.append( qpolygon )
          geom = QgsCore.QgsGeometry.fromMultiPolygon( qmultipolygon )
        del itemResponse['data_geometry'] 
        vFields[ fields[3] ] = API_RP.getHtmlTreeMetadata( itemResponse, '')
        vjson = json.dumps(  itemResponse )
        vFields[ fields[4] ] = vjson
        vFields[ fields[5] ] = len( vjson)
        feat = QgsCore.QgsFeature()
        if not geom is None:
          feat.setGeometry( geom )
        atts = map( lambda item: vFields[ item ], fields )
        feat.setAttributes( atts )
        return feat

      def commitFeatures(features):
        if not self.layer is None and len( features ) > 0:
          self.layer.startEditing()
          prov = self.layer.dataProvider()
          prov.addFeatures( features )
          self.layer.commitChanges()
          self.layer.updateExtents()

      def createRubberBand():

        def canvasRect( ):
          # Adaption from "https://github.com/sourcepole/qgis-instantprint-plugin/blob/master/InstantPrintTool.py" 
          mtp  = self.canvas.mapSettings().mapToPixel()
          rect = self.canvas.extent().toRectF()
          p1 = mtp.transform( QgsCore.QgsPoint( rect.left(), rect.top() ) )
          p2 = mtp.transform( QgsCore.QgsPoint( rect.right(), rect.bottom() ) )
          return QtCore.QRect( p1.x(), p1.y(), p2.x() - p1.x(), p2.y() - p1.y() )

        rb = QgsGui.QgsRubberBand( self.canvas, False )
        rb.setBorderColor( QtGui.QColor( 0, 255 , 255 ) )
        rb.setWidth( 2 )
        rb.setToCanvasRectangle( canvasRect() )
        return rb

      def extentFilter():
        crsCanvas = self.canvas.mapSettings().destinationCrs()
        crsLayer = self.layer.crs()
        ct = QgsCore.QgsCoordinateTransform( crsCanvas, crsLayer )
        extent = self.canvas.extent() if crsCanvas == crsLayer else ct.transform( self.canvas.extent() )
        return json.loads( QgsCore.QgsGeometry.fromRect( extent ).exportToGeoJSON() )

      def finished():
        self.canvas.scene().removeItem( rb )
        if not self.hasCriticalMessage:
          self.msgBar.popWidget()
          
        if self.layer is None:
          return

        msg = "Finished the search of images. Found {} images"
        typeMessage = QgsGui.QgsMessageBar.INFO
        if self.mbcancel.isCancel:
          self.msgBar.popWidget()
          if self.layer is None:
            removeFeatures()
          typeMessage = QgsGui.QgsMessageBar.WARNING
          msg = "Canceled the search of images. Removed {} features"
        msg = msg.format( self.stepProcessing )
        self.msgBar.pushMessage( CatalogRP.pluginName, msg, typeMessage, 4 )

      date1 = self.settings['date1']
      date2 = self.settings['date2']
      days = date1.daysTo( date2)
      date1, date2 = date1.toString( QtCore.Qt.ISODate ), date2.toString( QtCore.Qt.ISODate )

      self.msgBar.clearWidgets()
      msg = "Starting the search of images - %s(%d days)..." % ( date2, days )
      self.mbcancel = MessageBarCancel( CatalogRP.pluginName, self.msgBar, msg, self.apiServer.kill )
      rb = createRubberBand() # Show Rectangle of Query (coordinate in pixel)

      satellite = self.settings['satellite']
      geojsonRequest = extentFilter()
      requestScenes( satellite, date1, date2, geojsonRequest ) # Populate self.scenesResponse
      if self.hasCriticalMessage:
        self.canvas.scene().removeItem( rb )
        return
      totalImage = len( self.scenesResponse )
      if totalImage == 0:
        self.canvas.scene().removeItem( rb )
        msg = "Not found images"
        self.msgBar.popWidget()
        self.msgBar.pushMessage( CatalogRP.pluginName, msg, QgsGui.QgsMessageBar.WARNING, 2 )
        return
      if self.scenesFound > totalImage:
        self.canvas.scene().removeItem( rb )
        msg = "Exceeded the total for request. Please select a less area in map."
        self.msgBar.popWidget()
        self.msgBar.pushMessage( CatalogRP.pluginName, msg, QgsGui.QgsMessageBar.WARNING, 2 )
        return

      self.msgBar.popWidget()
      msg = "Creating {} catalog ({} total)".format( satellite, totalImage )
      self.mbcancel = MessageBarCancel( CatalogRP.pluginName, self.msgBar, msg, self.apiServer.kill )

      self.stepProcessing = 0
      features = []
      fields = [ 'id', 'acquired', 'thumbnail', 'meta_html', 'meta_json', 'meta_jsize' ] # See FIELDs order from createLayer
      for item in self.scenesResponse:
        if self.mbcancel.isCancel or self.layer is None :
          break
        features.append( getFeature(item, fields ) )
        msg = "Adding {}/{} features...".format( self.stepProcessing, totalImage  )
        self.mbcancel.message( msg )
        self.stepProcessing += 1

      commitFeatures( features )
      del features[:]
      finished()

    if not hasSettingPath():
      return
    
    self.enableRun.emit( False )

    # Setting Layer
    if not self.layer is None:
      QgsCore.QgsMapLayerRegistry.instance().removeMapLayer( self.layer.id() )
    
    createLayer() 
    self.hasCriticalMessage = False
    populateLayer() # addFeatures().commitFeatures() -> QtCore.QEventLoop()
    if not self.layer is None:
      self.legendCatalogLayer.setLayer( self.layer )
    self.enableRun.emit( True )

  def settingImages(self):
    def addSizeTMS():
      if self.settings['path'] == DialogCatalogSettingRP.titleSelectDirectory:
        self.settings['size_tms'] = 0
      else:
        self.settings['size_tms'] = DialogCatalogSettingRP.getSizeTMS( self.settings['path'] )

    msg = "Calculating TMS cache..."
    self.msgBar.pushMessage( self.pluginName, msg, QgsGui.QgsMessageBar.INFO )
    addSizeTMS()
    self.msgBar.popWidget()
    dlg = DialogCatalogSettingRP( self.mainWindow, self.icon, self.settings )
    if dlg.exec_() == QtGui.QDialog.Accepted:
      self.settings = dlg.getData()

  @QtCore.pyqtSlot(str)
  def layerWillBeRemoved(self, id):
    if not self.layer is None and id == self.layer.id():
      self.apiServer.kill()
      self.worker.kill()
      self.legendCatalogLayer.clean()
      self.layer = None

  @QtCore.pyqtSlot()
  def CreateTMS_GDAL_WMS(self):
    def setGroupCatalog():
      def existsGroupCatalog():
        groups = [ n for n in root.children() if n.nodeType() == QgsCore.QgsLayerTreeNode.NodeGroup ]
        return self.catalog['ltg'] in groups

      def createGroupCatalog():
        self.catalog['satellite'] = self.settings['satellite']
        self.catalog['ltg'] = root.addGroup( 'Calculating...' )

      root = QgsCore.QgsProject.instance().layerTreeRoot()
      if self.catalog['ltg'] is None:
        createGroupCatalog()
      if not self.catalog['satellite'] == self.settings['satellite']:
        createGroupCatalog()
      if not existsGroupCatalog():
        createGroupCatalog()
      else:
        self.catalog['ltg'].removeAllChildren()

    def sortGroupCatalog(reverse=True):
      def getLayers():
        ltls = self.catalog['ltg'].findLayers()
        if len( ltls ) == 0:
          return
        # Sort layer
        d_name_layerd = {}
        for ltl in ltls:
          layer = ltl.layer()
          name = layer.name()
          d_name_layerd[ name ] = layer
        l_name_sorted = sorted( d_name_layerd.keys() )
        #
        layers = [ d_name_layerd[ name] for name in  l_name_sorted ]
  
        return layers
  
      def getGroupsDate(layers):
        groupDates =  {} # 'date': layers }
        for l in layers:
          date = l.customProperty('date', '_errorT').split('T')[0]
          if not date in groupDates.keys():
            groupDates[ date ] = [ l ]
          else:
            groupDates[ date ].append( l )
        return groupDates
  
      def addGroupDates(groupDates):
        keys = sorted(groupDates.keys(), reverse=reverse )
        for idx, key in enumerate( keys ):
          name = "{0} [{1}]".format( key, len( groupDates[ key ] ) )
          ltg = self.catalog['ltg'].insertGroup( idx, name )
          for l in groupDates[ key ]:
            ltg.addLayer( l ).setVisible( QtCore.Qt.Unchecked )
          ltg.setExpanded(False)
        self.catalog['ltg'].removeChildren( len( keys), len( layers) )
  
      def setNameGroupCatalog(total):
        rgb = ','.join( self.settings['rgb'] )
        name = "{} Catalog {} ({}) [{}]".format( self.catalogName, self.catalog['satellite'], rgb, total )
        self.catalog['ltg'].setName( name )

      layers = getLayers()
      groupDates = getGroupsDate( layers )
      addGroupDates( groupDates )
      setNameGroupCatalog( len( groupDates ) )

    @QtCore.pyqtSlot( dict )
    def finished( message ):
      self.thread.quit()
      self.worker.finished.disconnect( finished )
      sortGroupCatalog()
      self._endProcessing( "Create TMS", message['totalError'] )

    setGroupCatalog()

    r = self._startProcess( self.worker.kill )
    if not r['isOk']:
      return
    iterFeat = r['iterFeat']

    if not os.path.exists( self.settings['path'] ):
      os.makedirs( self.settings['path'] )
    cr3857 = QgsCore.QgsCoordinateReferenceSystem( 3857, QgsCore.QgsCoordinateReferenceSystem.EpsgCrsId )
    ctTMS = QgsCore.QgsCoordinateTransform( self.layer.crs(), cr3857 )

    self.worker.finished.connect( finished )
    data = {
      'pluginName': CatalogRP.pluginName,
      'getURL': self.apiServer.getURL_TMS, 
      'path': self.settings['path'],
      'rgb': self.settings['rgb'],
      'ltgCatalog': self.catalog['ltg'],
      'id_layer': self.layer.id(),
      'ctTMS': ctTMS,
      'iterFeat': iterFeat # feat: 'id', 'acquired', 'meta_json'
    }
    self.worker.setting( data )
    self.worker.stepProgress.connect( self.mbcancel.step )
    #self.thread.start() # Start Worker
    self.worker.run()    # DEBUGER

  @staticmethod
  def copyExpression():
    dirname = os.path.dirname
    fromExp = os.path.join( dirname( __file__ ), CatalogRP.expressionFile )
    dirExp = os.path.join( dirname( dirname( dirname( __file__ ) ) ), CatalogRP.expressionDir )
    toExp = os.path.join( dirExp , CatalogRP.expressionFile )
    if os.path.isdir( dirExp ):
      if QtCore.QFile.exists( toExp ):
        QtCore.QFile.remove( toExp ) 
      QtCore.QFile.copy( fromExp, toExp ) 
