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

import os, json, math

from PyQt4 import QtCore, QtGui

from apiqtcatalog import API_Catalog
from catalogimage import CatalogImage
from legendlayercatalog import DialogCatalogSetting


class API_RP(API_Catalog):
  def __init__(self):
    self.satellites = ['landsat-8', 'sentinel-2']    
    l_url = [
      'https://api.developmentseed.org/satellites/?limit=2000',
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
    super( API_RP, self ).__init__()

  def _getSatelliteProductId(self, meta_json, sbands ):
    satellite = meta_json['satellite_name']
    if not satellite == 'landsat-8':
      satellite = 'sentinel-2' # satellite_name = Sentinel-2A
      id = meta_json['scene_id'] 
    else:
      id = meta_json['product_id']
    return ( satellite, id, ','.join( sbands).replace('B', '') )

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
    self.requestForJson( url, setFinished )

  def existImage(self, meta_json,  sbands):
    def setFinished(response):
      if not response['isOk']:
        msg = response['message']
        if not self.isKilled():
          substring = "server replied:"
          msg = msg[ msg.index( substring ) + len( substring ) + 1 : ]
          response['message'] = msg
        del response['errorCode']
        self.response = response
      elif response['isJSON']:
        response['isOk'] = False
        self.response = response
      else:
        self.response = { 'isOk': True }
      loop.quit()

    self.response = None
    loop = QtCore.QEventLoop()
    ( satellite, id, rgb ) = self._getSatelliteProductId( meta_json, sbands )
    tile = meta_json['TMS']['minimum_tile']
    zxy = "{z}/{x}/{y}".format( z=tile['z'], x=tile['x'], y=tile['y'] )
    url = "{url}/tiles/{{product_id}}/{{zxy}}.png?rgb={{rgb}}&tile=256&pan=true".format( url=self.urlImages[ satellite ] )
    url = url.format( product_id=id, zxy=zxy,rgb=rgb)
    super( API_RP, self ).requestForJson( url, setFinished)
    loop.exec_()
    return  self.response

  def getURL_TMS(self, feat, sbands):
    meta_json = json.loads( feat['meta_json'] )
    ( satellite, id, rgb ) = self._getSatelliteProductId( meta_json, sbands )
    url = "{url}/tiles/{{product_id}}/{{xyz}}.png?rgb={{rgb}}&tile=256&pan=true".format( url=self.urlImages[ satellite ] )
    url = url.format( product_id=id, xyz='{z}/{x}/{y}',rgb=rgb)
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
    

class CatalogRP(CatalogImage):
  def __init__(self, icon):
    super(CatalogRP, self).__init__( icon, u'Catalog Remote Pixel')
    self.styleFile = 'rp_scenes.qml'
    self.catalogName = "Remote Pixel"
    self.nameThread = "QGIS_Plugin_Catalog_RP"
    self.apiServer = API_RP()
    self.settings = DialogCatalogSettingRP.getSettings( DialogCatalogSettingRP.configQGIS )
    self.settings['satellite'] = 'landsat-8'
    self.settings['rgb'] = DialogCatalogSettingRP.getVegetationBands( self.settings['satellite'] )

  def settingImages(self):
    super(CatalogRP, self).settingImages()
    dlg = DialogCatalogSettingRP( self.mainWindow, self.icon, self.settings )
    if dlg.exec_() == QtGui.QDialog.Accepted:
      self.settings = dlg.getData()
