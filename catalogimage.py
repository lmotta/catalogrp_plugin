# -*- coding: utf-8 -*-
"""
/***************************************************************************
Name                 : Catalog Image
Description          : Base Class for Catalog
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

import os, json, math

from PyQt4 import QtCore, QtGui
from qgis import core as QgsCore, gui as QgsGui, utils as QgsUtils

from apiqtcatalog import API_Catalog
from legendlayercatalog import ( DialogCatalogSetting, LegendCatalogLayer )
from legendlayerraster import LegendRasterGeom
from messagebarcancel import MessageBarCancel, MessageBarCancelProgress
from workertms import WorkerCreateTMS_GDAL_WMS 

# Base Class
class CatalogImage(QtCore.QObject):
  enableRun = QtCore.pyqtSignal( bool )
  def __init__(self, icon, pluginName):
    super(CatalogImage, self).__init__()
    self.pluginName = pluginName
    # Set by derivade Class
    self.styleFile = None
    self.catalogName = None
    self.nameThread = None
    self.apiServer = None
    self.pairkeys = None
    self.geomKey = None
    self.settings = None
    #
    self.canvas = QgsUtils.iface.mapCanvas()
    self.msgBar = QgsUtils.iface.messageBar()
    self.logMessage = QgsCore.QgsMessageLog.instance().logMessage
    self.icon = icon
    self.mainWindow = QgsUtils.iface.mainWindow()

    self.legendRasterGeom = LegendRasterGeom( self.pluginName )
    self.thread = self.worker = None # initThread
    self.mbcancel = None # Need for worker
    self.isHostLive = False

    self.layer = None
    self.hasCriticalMessage = None
    self.scenesResponse, self.scenesFound = None, None
    self.messageProcess = self.isOkProcess = None
    self.currentItem, self.stepProcessing = None, None
    self.catalog = { 'ltg': None, 'satellite': None }

    arg = ( self.pluginName, self.createTMS_GDAL_WMS, self.verifyTMS )
    self.legendCatalogLayer = LegendCatalogLayer( *arg )
    
    self._connect()
    self._initThread()

  def __del__(self):
    self._connect( False )
    self._finishThread()
    del self.legendRasterGeom

  def _initThread(self):
    self.thread = QtCore.QThread( self )
    self.thread.setObjectName( self.nameThread )
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
      arg = ( self.pluginName, msg, QgsGui.QgsMessageBar.WARNING, 4 ) 
      self.msgBar.pushMessage( *arg )
      return { 'isOk': False }

    msg = "selected" if hasSelected else "all"
    msg = "Processing {0} images({1})...".format( totalFeat, msg )
    arg = ( self.pluginName, self.msgBar, msg, totalFeat, funcKill, hasProgressFile )
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
      arg = ( self.pluginName, msg, QgsGui.QgsMessageBar.CRITICAL, 4 )
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
      if self.settings['path'] == DialogCatalogSetting.titleSelectDirectory:
        msg = "Please, {0}".format( DialogCatalogSetting.titleSelectDirectory )
        self.msgBar.pushMessage( self.pluginName, msg, QgsGui.QgsMessageBar.WARNING, 6 )
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
      ns = os.path.join( os.path.dirname( __file__ ), self.styleFile )
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
          self.msgBar.pushMessage( self.pluginName, self.messageProcess, QgsGui.QgsMessageBar.CRITICAL, 4 )
          self.messageProcess = None
          self.scenesResponse = None

      def getFeature(itemResponse, fields):
        def getMinTileXYZ(geom, z):
          extent = geom.boundingBox()
          ( lat, long ) = ( extent.yMaximum(), extent.xMinimum() )
          if lat == long and lat == 0:
            return { 'x': 0, 'y': 0, 'z': 0 }
          lat_rad = math.radians( lat )
          n = 2.0 ** z
          x = int( ( long + 180.0) / 360.0 * n)
          y = int( ( 1.0 - math.log( math.tan( lat_rad ) + ( 1 / math.cos( lat_rad ) ) ) / math.pi ) / 2.0 * n )
          return { 'x': x, 'y': y, 'z': z }

        # Fields
        # 'id', 'acquired', 'thumbnail', 'meta_html', 'meta_json', 'meta_jsize'
        vFields =  { }
        for k, v in self.pairkeys.items():
          vFields[ k ] = itemResponse[ v ]
        del itemResponse['thumbnail']
        # Geom
        geom = None
        geomItem = itemResponse[ self.geomKey ]
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
        del itemResponse[ self.geomKey ]
        #
        itemResponse['TMS'] = {
          'isOk': True,
          'hasChecking': False,
          'minimum_tile': getMinTileXYZ( geom, 8 )
        }
        vFields[ fields[3] ] = API_Catalog.getHtmlTreeMetadata( itemResponse, '')
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

        msg = "Finished the search of images. Found {} images (some images may not have the TMS)"
        typeMessage = QgsGui.QgsMessageBar.INFO
        if self.mbcancel.isCancel:
          self.msgBar.popWidget()
          removeFeatures()
          typeMessage = QgsGui.QgsMessageBar.WARNING
          msg = "Canceled the search of images. Removed {} features"

        msg = msg.format( self.stepProcessing )
        self.msgBar.pushMessage( self.pluginName, msg, typeMessage, 4 )

      date1 = self.settings['date1']
      date2 = self.settings['date2']
      days = date1.daysTo( date2)
      date1, date2 = date1.toString( QtCore.Qt.ISODate ), date2.toString( QtCore.Qt.ISODate )

      self.msgBar.clearWidgets()
      msg = "Starting the search of images - {}({} days)...".format( date2, days )
      self.mbcancel = MessageBarCancel( self.pluginName, self.msgBar, msg, self.apiServer.kill )
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
        self.msgBar.pushMessage( self.pluginName, msg, QgsGui.QgsMessageBar.WARNING, 2 )
        return
      if self.scenesFound > totalImage:
        del self.scenesResponse[:]
        self.canvas.scene().removeItem( rb )
        msg = "Exceeded the limit for request({}), return {}. Please select a less area in map."
        msg = msg.format( totalImage, self.scenesFound )
        self.msgBar.popWidget()
        self.msgBar.pushMessage( self.pluginName, msg, QgsGui.QgsMessageBar.WARNING, 4 )
        return

      self.msgBar.popWidget()
      msg = "Creating {} catalog ({} total)".format( satellite, totalImage )
      self.mbcancel = MessageBarCancel( self.pluginName, self.msgBar, msg, self.apiServer.kill )

      self.stepProcessing = 0
      features = []
      fields = [ 'id', 'acquired', 'thumbnail', 'meta_html', 'meta_json', 'meta_jsize' ] # See FIELDs order from createLayer
      for item in self.scenesResponse:
        if self.mbcancel.isCancel or self.layer is None :
          break
        feat  =  getFeature( item, fields )
        features.append( feat )
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
      if self.settings['path'] == DialogCatalogSetting.titleSelectDirectory:
        self.settings['size_tms'] = 0
      else:
        self.settings['size_tms'] = DialogCatalogSetting.getSizeTMS( self.settings['path'] )

    msg = "Calculating TMS cache..."
    self.msgBar.pushMessage( self.pluginName, msg, QgsGui.QgsMessageBar.INFO )
    addSizeTMS()
    self.msgBar.popWidget()
####  Derivated class
#     super(CatalogRP, self).settingImages()
#     dlg = DialogCatalogSetting??( self.mainWindow, self.icon, self.settings )
#     if dlg.exec_() == QtGui.QDialog.Accepted:
#       self.settings = dlg.getData()
###

  @QtCore.pyqtSlot(str)
  def layerWillBeRemoved(self, id):
    if not self.layer is None and id == self.layer.id():
      self.apiServer.kill()
      self.worker.kill()
      self.legendCatalogLayer.clean()
      self.layer = None

  @QtCore.pyqtSlot()
  def createTMS_GDAL_WMS(self):
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
          return []
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
      if len( layers ) == 0:
        rgb = ','.join( self.settings['rgb'] )
        name = "{} Catalog {} ({}) [{}]".format( self.catalogName, self.catalog['satellite'], rgb, 0 )
        self.catalog['ltg'].setName( name )
        return
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
      'pluginName': self.pluginName,
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

  @QtCore.pyqtSlot()
  def verifyTMS(self):
    #
    # Fields = { 0 : 'id', 1: 'acquired', 2 : 'thumbnail', 3: 'meta_json',
    #            4: 'meta_html', 5: 'meta_jsize' }
    #
    def finished(totalCommit, totalNoTMS, typeImage):
      self.msgBar.popWidget()
      typeMessage = QgsGui.QgsMessageBar.INFO
      msg = ''
      if self.mbcancel.isCancel or self.layer is None:
        msg = "Canceled by User"
        typeMessage = QgsGui.QgsMessageBar.WARNING
      elif totalCommit == 0:
        msg = "All images already were checked ({})".format( typeImage )
      else:
        if totalNoTMS > 0:
          msg = "Checked TMS. Found {} images doesn't have TMS({})".format( totalNoTMS, typeImage )
          typeMessage = QgsGui.QgsMessageBar.WARNING
        else:
          msg = "Checked TMS({})".format( typeImage )
      self.msgBar.pushMessage( self.pluginName, msg, typeMessage, 4 )
      self.legendCatalogLayer.selectionChanged()

    typeImage = 'selected'
    getFeatures = self.layer.selectedFeaturesIterator
    total = self.layer.selectedFeatureCount()
    if total == 0:
       getFeatures = self.layer.getFeatures
       total = self.layer.featureCount()
       typeImage = 'total'
       
    self.msgBar.clearWidgets()
    msg = "Checking TMS {} images({})...".format( total, typeImage )
    self.mbcancel = MessageBarCancel( self.pluginName, self.msgBar, msg, self.apiServer.kill )

    request = QgsCore.QgsFeatureRequest().setFlags( QgsCore.QgsFeatureRequest.NoGeometry )
    fields = ['meta_html', 'meta_json', 'meta_jsize']
    request = request.setSubsetOfAttributes( fields, self.layer.pendingFields() )
    iter = getFeatures( request )
    self.layer.startEditing()
    prov = self.layer.dataProvider()
    totalNoTMS, totalCommit = 0, 0
    step = 0
    for feat in iter:
      step += 1
      if self.mbcancel.isCancel or self.layer is None :
        break
      msg = "Checking TMS {}/{} images({}).".format( step, total, typeImage )
      self.mbcancel.message( msg )
      meta_json = json.loads( feat['meta_json'] )
      if meta_json['TMS']['hasChecking']:
        continue
      totalCommit += 1
      meta_json['TMS']['hasChecking'] = True
      r = self.apiServer.existImage( meta_json, self.settings['rgb'] )
      meta_json['TMS']['isOk'] = r['isOk']
      if not r['isOk']:
         meta_json['TMS']['message'] = r['message']
         totalNoTMS += 1
      meta_html  = API_Catalog.getHtmlTreeMetadata( meta_json, '')
      meta_json  = json.dumps(  meta_json )
      meta_jsize = len( meta_json )
      attrs = { 3 : meta_html, 4 : meta_json, 5: meta_jsize }
      prov.changeAttributeValues( { feat.id() : attrs } )
    self.layer.commitChanges()
    finished(totalCommit, totalNoTMS, typeImage)
    
