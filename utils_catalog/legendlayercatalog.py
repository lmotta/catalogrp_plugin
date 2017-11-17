# -*- coding: utf-8 -*-
"""
/***************************************************************************
Name                 : Catalog Dialog and Layer
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

import os, shutil

from PyQt4 import QtCore, QtGui, QtXml
from qgis import core as QgsCore, gui as QgsGui, utils as QgsUtils
from apiqtcatalog import API_Catalog

class DialogCatalogSetting(QtGui.QDialog):
  titleSelectDirectory = "Select directory for TMS"
  def __init__(self, parent, icon, dataSetting, satellites, configQGIS, getVegetationBands):
    def initGui():
      def setData():
        w = self.findChild( QtGui.QRadioButton, self.data['satellite'] )
        w.setChecked(True)
        self._populateRGB( self.data['satellite'] )
        buttonPath.setText( self.data['path'] )
        buttonClearCache.setText( self.titleClearCache.format( self.data['size_tms'] ) )
        if self.data['size_tms'] > 0:
          buttonClearCache.setEnabled(True)
        d1 = self.data['date1']
        d2 = self.data['date2']
        date1.setDate( d1 )
        date2.setDate( d2 )
        date1.setMaximumDate( d2.addDays( -1 ) )
        date2.setMinimumDate( d1.addDays( +1 ) )
        spinDay.setValue( d1.daysTo( d2) )

      def connect():
        buttonOK.clicked.connect( self.onOK )
        buttonPath.clicked.connect( self.onPath )
        buttonClearCache.clicked.connect( self.onClearCache )
        date1.dateChanged.connect( self.onDateChanged1 )
        date2.dateChanged.connect( self.onDateChanged2 )
        spinDay.valueChanged.connect( self.onValueChanged )

      def createDateEdit(labelName, objName, group, layout):
        label = QtGui.QLabel( labelName, group )
        layout.addWidget( label )
        widget = QtGui.QDateEdit( group )
        widget.setObjectName( objName )
        widget.setCalendarPopup( True )
        format = widget.displayFormat().replace('yy', 'yyyy')
        widget.setDisplayFormat( format )
        layout.addWidget( widget )
        return widget

      def createRadioButton(text, tip, objName, group, layout=None):
        w = QtGui.QRadioButton( text, group )
        w.clicked.connect( self.onSatellite )
        w.setToolTip( tip )
        w.setObjectName( objName )
        if not layout is None:
          layout.addWidget( w )

      windowTitle = "Setting Remote Pixel"
      self.setWindowTitle( windowTitle )
      self.setWindowIcon( icon )

      grpImage = QtGui.QGroupBox('Images', self )
      lytSatellite = QtGui.QHBoxLayout()
      for name in sorted( self.satellites.keys() ):
        d,b =   self.satellites[ name ]['dates'], str( self.satellites[ name ]['bands'] )
        tip = "{}\nBands: {}".format( d, b )
        arg = ( name.capitalize(), tip, name,  grpImage, lytSatellite )
        createRadioButton( *arg )
        
      lytRGB = QtGui.QHBoxLayout()
      lytRGB.addWidget( QtGui.QLabel('RGB:') )
      for name in 'RGB':
        w = QtGui.QComboBox( grpImage )
        w.setObjectName( name )
        lyt = QtGui.QHBoxLayout()
        lyt.addWidget( w )
        lytRGB.addLayout( lyt )

      buttonPath = QtGui.QPushButton( DialogCatalogSetting.titleSelectDirectory, grpImage )
      buttonPath.setObjectName('path')

      text = "Clear TMS cache (total calculating..)" 
      buttonClearCache = QtGui.QPushButton( text, grpImage )
      buttonClearCache.setObjectName('clear_cache')
      buttonClearCache.setEnabled(False)

      lytImage = QtGui.QVBoxLayout( grpImage )
      lytImage.addLayout( lytSatellite )
      lytImage.addLayout( lytRGB)
      lytImage.addWidget( buttonPath )
      lytImage.addWidget( buttonClearCache )

      grpDateSearch = QtGui.QGroupBox('Dates for search', self )
      lytDate = QtGui.QHBoxLayout( grpDateSearch )
      date1 = createDateEdit('From', 'deDate1', grpDateSearch, lytDate )
      date2 = createDateEdit('To', 'deDate2', grpDateSearch, lytDate )
      spinDay = QtGui.QSpinBox( grpDateSearch )
      spinDay.setObjectName('sbDay')
      spinDay.setSingleStep( 1 )
      spinDay.setSuffix(' Days')
      spinDay.setRange( 1, 1000*360 )
      lytDate.addWidget( spinDay )

      buttonOK = QtGui.QPushButton('OK', self )

      layout = QtGui.QVBoxLayout( self )
      layout.addWidget( grpImage )
      layout.addWidget( grpDateSearch )
      layout.addWidget( buttonOK )

      self.resize( 5 * len( windowTitle ) + 200 , 30 )

      setData()
      connect()

    super( DialogCatalogSetting, self ).__init__( parent )
    self.data, self.satellites  = dataSetting, satellites
    self.configQGIS, self.getVegetationBands = configQGIS, getVegetationBands
    self.titleClearCache = "Clear TMS cache (total {:0.2f}MB)"
    initGui()

  def getData(self):
    return self.data

  def _populateRGB(self, satellite):
     bands = self.satellites[ satellite ]['bands']
     id = 0
     for c in 'RGB':
       w = self.findChild( QtGui.QComboBox, c)
       w.clear()
       w.addItems( bands )
       idxBand = bands.index( self.data['rgb'][ id ] )
       w.setCurrentIndex( idxBand )
       id += 1

  def _saveDataSetting(self):
    # Next step add all informations
    #See __init__.initGui
    #keys = ['path', 'landsat-8', 'sentinel2', 'date1', 'date2']

    keys = ['path' ]
    values = {}
    for k in keys:
      values[ k ] = "{0}/{1}".format( self.configQGIS, k )
    s = QtCore.QSettings()
    for k in values.keys():
      s.setValue( values[ k ], self.data[ k ] )

  def _setSpinDay(self,  date1, date2 ):
    spinDay = self.findChild( QtGui.QSpinBox, "sbDay" )
    spinDay.valueChanged.disconnect( self.onValueChanged )
    spinDay.setValue( date1.daysTo( date2) )
    spinDay.valueChanged.connect( self.onValueChanged )

  @staticmethod
  def getSettings(configQGIS):
    # Next step add all informations
    #See __init__.initGui
    #keys = ['path', 'satellite', 'date1', 'date2', 'rgb' ]
    keys = ['path']
    values = {}
    for k in keys:
      values[ k ] = "{0}/{1}".format( configQGIS, k )
    s = QtCore.QSettings()
    data = {}
    # Path
    path = s.value( values['path'], None )
    if not path is None:
      if QtCore.QDir( path ).exists():
        data['path'] = path
      else:
        data['path'] = DialogCatalogSetting.titleSelectDirectory 
        s.remove( values['path'] )
    else:
      data['path'] = DialogCatalogSetting.titleSelectDirectory
    #
    data['satellite'], data['rgb'] = None, None # set after return. Will be change when add all informations
    #
    data['date2'] = QtCore.QDate.currentDate()
    data['date1'] = data['date2'].addMonths( -1 )

    return data

  @staticmethod
  def getDirsCacheTMS(path):
    if not os.path.isdir( path ):
      return None, []
    
    absdir = lambda d: os.path.join( path, d)
    return [ absdir( d) for d in os.listdir( path ) if os.path.isdir( absdir( d ) ) ]

  @staticmethod
  def getSizeTMS(path):
    total_size = 0
    # Files(XMLs)
    absdir = lambda d: os.path.join( path, d)
    for f in os.listdir( path ):
      if os.path.isfile( absdir( f ) ):
        total_size += os.path.getsize( absdir( f ) ) / 1024.0
    # Directories TMS
    dirs = DialogCatalogSetting.getDirsCacheTMS( path )
    if len( dirs ) == 0:
      return total_size
    for item in dirs: 
      for dirpath, dirnames, filenames in os.walk( item ):
        total_size += os.path.getsize(dirpath) / 1024.0 # KB
        for f in filenames:
          fp = os.path.join( dirpath, f )
          total_size += os.path.getsize(fp) / 1024.0 # KB
    return total_size/1024.0   # in MB

  @QtCore.pyqtSlot()
  def onOK(self):
    def getCurrentSatellite():
      for name in self.satellites.keys():
        w = self.findChild( QtGui.QRadioButton, name )
        if w.isChecked():
          return name

    def getRGB():
      srgb = []
      for b in 'RGB':
        w = self.findChild( QtGui.QComboBox, b )
        srgb.append( str( w.currentText() ) )
      return srgb

    pb = self.findChild( QtGui.QPushButton, 'path' )
    path = pb.text()
    if path == DialogCatalogSetting.titleSelectDirectory:
      msg = "Please, {0}".format( self.titleSelectDirectory )
      QtGui.QMessageBox.information( self, "Missing directory for download", msg )
      return
    date1 = self.findChild( QtGui.QDateEdit, "deDate1" )
    date2 = self.findChild( QtGui.QDateEdit, "deDate2" )
    satellite = getCurrentSatellite()
    self.data = {
        'path': path,
        'satellite': satellite,
        'rgb': getRGB(),
        'date1': date1.date(),
        'date2': date2.date()
    }
    self._saveDataSetting()
    self.data['isOk'] = True
    self.accept()

  @QtCore.pyqtSlot()
  def onPath(self):
    w = self.findChild( QtGui.QPushButton, 'path' )
    path = w.text()
    if path == DialogCatalogSetting.titleSelectDirectory:
      path = None
    sdir = QtGui.QFileDialog.getExistingDirectory(self, DialogCatalogSetting.titleSelectDirectory, path )
    if len(sdir) > 0:
      w.setText( sdir )

  @QtCore.pyqtSlot()
  def onClearCache(self):
    # Get path
    w = self.findChild( QtGui.QPushButton, 'path' )
    path = w.text()
    # Remove Files(XML)
    absdir = lambda d: os.path.join( path, d)
    [ os.remove( absdir( f ) ) for f in os.listdir( path ) if os.path.isfile( absdir( f ) ) ]
    # Remove Directories
    dirs = DialogCatalogSetting.getDirsCacheTMS( path )
    if not len( dirs ) == 0:
      for d in dirs:
        shutil.rmtree(d)
    title = self.titleClearCache.format(0)
    w = self.findChild( QtGui.QPushButton, 'clear_cache' )
    w.setText( title )
    w.setEnabled(False)

  @QtCore.pyqtSlot( QtCore.QDate )
  def onDateChanged1(self, date ):
    date2 = self.findChild( QtGui.QDateEdit, "deDate2" )
    date2.setMinimumDate( date.addDays( +1 ) )
    self._setSpinDay( date, date2.date() )

  @QtCore.pyqtSlot( QtCore.QDate )
  def onDateChanged2(self, date ):
    date1 = self.findChild( QtGui.QDateEdit, "deDate1" )
    date1.setMaximumDate( date.addDays( -1 ) )
    self._setSpinDay( date1.date(), date )

  @QtCore.pyqtSlot( bool )
  def onSatellite(self, checked):
    if checked:
      w = self.sender()
      satellite = w.objectName()
      self.data['rgb'] = self.getVegetationBands( satellite )
      self._populateRGB( satellite )

  @QtCore.pyqtSlot( int )
  def onValueChanged(self, days ):
    date1 = self.findChild( QtGui.QDateEdit, "deDate1" )
    date2 = self.findChild( QtGui.QDateEdit, "deDate2" )
    newDate = date2.date().addDays( -1 * days )
    date1.dateChanged.disconnect( self.onDateChanged1 )
    date1.setDate( newDate )
    date2.setMinimumDate( newDate.addDays( +1 ) )
    date1.dateChanged.connect( self.onDateChanged1 )

class LegendCatalogLayer():
  def __init__(self, labelMenu, slotTMS, slotVerifyTMS):
    self.slots = { 'create_tms': slotTMS, 'verify_tms': slotVerifyTMS } 
    self.labelMenu, self.slotTMS, self.slotVerifyTMS = labelMenu, slotTMS, slotVerifyTMS
    self.legendInterface = QgsUtils.iface.legendInterface()
    self.layer, self.legendLayer = None, None

  def _getLabelsTMS(self, prefixLabelCreate, prefixLabelVerify):
    def getNoTMS(getFeatures):
      request = QgsCore.QgsFeatureRequest().setFlags( QgsCore.QgsFeatureRequest.NoGeometry )
      request.setSubsetOfAttributes( ['meta_html'], self.layer.pendingFields() )
      iter = getFeatures( request )
      noTMS = 0
      for feat in iter:
        ( isOk, hasTMS ) = API_Catalog.getValue( feat['meta_json'], ['TMS','isOk'])
        if  not hasTMS:
          noTMS += 1
      return noTMS

    totaSelected = self.layer.selectedFeatureCount()
    totalAll = self.layer.featureCount()
    suffixCreate = "{} total".format( totalAll )
    suffixVerify = "{} total".format( totalAll )
    c = "{} total".format( totalAll )
    if totaSelected > 0:
      noTMS = getNoTMS( self.layer.selectedFeaturesIterator )
      if noTMS > 0:
        suffixCreate = "{}/{} selected - {} without TMS".format( totaSelected, totalAll, noTMS )
      else:
        suffixCreate = "{}/{} selected".format( totaSelected, totalAll )
      suffixVerify = "{}/{} selected".format( totaSelected, totalAll )
    else:
      noTMS = getNoTMS( self.layer.getFeatures )
      if noTMS > 0:
        suffixCreate = "{} total - {} without TMS".format( totalAll,  noTMS )

    labelCreate = '{} ({})'.format( prefixLabelCreate, suffixCreate )
    labelVerify = '{} ({})'.format( prefixLabelVerify, suffixVerify )
    return labelCreate, labelVerify

  def clean(self):
    for item in self.legendLayer:
      self.legendInterface.removeLegendLayerAction( item['action'] )

  def setLayer(self, layer):
    def addActionLegendLayer():
      labelCreate, labelVerify = self._getLabelsTMS('Create TMS', 'Verify TMS')
      self.legendLayer = [
        {
          'menu': labelCreate,
          'id': 'idCreateTMS',
          'slot': self.slots['create_tms'],
          'action': None
        },
        {
          'menu': labelVerify,
          'id': 'idVerifyTMS',
          'slot': self.slots['verify_tms'],
          'action': None
        }
      ]
      for item in self.legendLayer:
        item['action'] = QtGui.QAction( item['menu'], self.legendInterface )
        item['action'].triggered.connect( item['slot'] )                        
        arg = ( item['action'], self.labelMenu, item['id'], QgsCore.QgsMapLayer.VectorLayer, False )
        self.legendInterface.addLegendLayerAction( *arg )
        self.legendInterface.addLegendLayerActionForLayer( item['action'], self.layer )

    self.layer = layer
    self.layer.selectionChanged.connect( self.selectionChanged )
    addActionLegendLayer()

  def enabledProcessing(self, enabled=True):
    for item in self.legendLayer:
      item['action'].setEnabled( enabled )

  @QtCore.pyqtSlot()
  def selectionChanged(self):
      labelCreate, labelVerify = self._getLabelsTMS('Create TMS', 'Verify TMS')
      self.legendLayer[0]['action'].setText(labelCreate )
      self.legendLayer[1]['action'].setText(labelVerify )
