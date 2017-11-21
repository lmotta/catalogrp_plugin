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

import json 

from PyQt4 import QtCore, QtGui

from utils_catalog.apiqtcatalog import API_Catalog
from utils_catalog.catalogimage import CatalogImage
from utils_catalog.legendlayercatalog import DialogCatalogSetting
from utils_catalog.managerregisterqgis import ManagerRegisterQGis


class API_RP(API_Catalog):
  def __init__(self):
    self.satellites = ['landsat-8', 'sentinel-2']
    keysSetting = { # ManagerRegisterQGis
      'landsat-8':  { 'order': 1, 'label': 'Landsat 8', 'isPassword': True },
      'sentinel-2': { 'order': 2, 'label': 'Sentinel 2', 'isPassword': True }
    }
    l_url = [
      'https://api.developmentseed.org/satellites/?limit=2000',
      'satellite_name={satellite}',
      'date_from={date_from}', 'date_to={date_to}',
      'intersects={geom}'
    ]
    self.urlSearch = '&'.join( l_url )
    self.urlImages = {
        'landsat-8': "https://{}.execute-api.us-west-2.amazonaws.com/production/landsat",
        'sentinel-2': "https://{}.execute-api.eu-central-1.amazonaws.com/production/sentinel"
    }
    self.response = None
    API_Catalog.__init__(self, keysSetting )

  def _getUrlImage(self, meta_json, sbands ):
    satellite = meta_json['satellite_name']
    if not satellite == 'landsat-8':
      satellite = 'sentinel-2' # satellite_name = Sentinel-2A
      id = meta_json['scene_id'] 
    else:
      id = meta_json['product_id']
    rgb = ','.join( sbands).replace('B', '')

    arg = ( self.urlImages[ satellite ], id, rgb)
    return "{}/tiles/{}/{{z}}/{{x}}/{{y}}.png?rgb={}&tile=256&pan=true".format( *arg )

  def _checkUrls(self, titleInvalid, urlKeys=None):
    def checkUrl(url):
      def setFinished(response):
        self.response = response
        loop.quit()
  
      loop = QtCore.QEventLoop()
      self.currentUrl = QtCore.QUrl( url )
      API_Catalog.isHostLive(self, setFinished )
      loop.exec_()

    totalOk = 0
    urlcheck = { }
    for satellite in self.urlImages.keys():
      urlcheck[ satellite ] = {}
      if urlKeys is None:
        url = self.urlImages[ satellite ]
      else:
        url = self.urlImages[ satellite ].format( urlKeys[ satellite ] ) 
      checkUrl( url )
      if self.response['isOk']:
        urlcheck[ satellite ]['isOk'] = True
        urlcheck[ satellite ]['url']  = url
        totalOk += 1 
      else:
        urlcheck[ satellite ]['isOk'] = False
    #
    response = {}
    if totalOk == len( self.urlImages.keys() ):
      response['isOk'] = True
    else:
      response['isOk'] = False
      errors = []
      for satellite in self.urlImages.keys():
        if not urlcheck[ satellite ]['isOk']:
          errors.append( satellite )
      response['message'] = "{}: {}".format( titleInvalid, ','.join( errors ) )
    return urlcheck, response

  def setKeys(self, urlKeys, setFinished):
    urlcheck, response = self._checkUrls('Invalid key(s)', urlKeys )
    if response['isOk']:
      for satellite in urlKeys.keys():
        self.urlImages[ satellite ] = urlcheck[ satellite ]['url']
    setFinished( response )

  def isHostLive(self, setFinished):
    urlcheck, response = self._checkUrls ('Host(s) not live')
    setFinished( response )

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
    DialogCatalogSetting.__init__(self,  *arg )

  @staticmethod
  def getVegetationBands(satellite):
    if satellite == 'landsat-8':
      return ['B6', 'B5', 'B4']
    else: # sentinel2
      return ['B11', 'B8A', 'B04']
    

class CatalogRP(CatalogImage):
  def __init__(self, parent, icon):
    self.parent, self.icon = parent, icon
    CatalogImage.__init__(self, u'Catalog Remote Pixel')
    self.catalogName = "Remote Pixel"
    self.nameThread = "QGIS_Plugin_Catalog_RP"
    self.apiServer = API_RP()
    self.pairkeys = { 'id': 'scene_id', 'acquired': 'date', 'thumbnail': 'thumbnail' }
    self.geomKey = 'data_geometry'
    self.settings = DialogCatalogSettingRP.getSettings( DialogCatalogSettingRP.configQGIS )
    self.settings['satellite'] = 'landsat-8'
    self.settings['rgb'] = DialogCatalogSettingRP.getVegetationBands( self.settings['satellite'] )
    title = "API Keys {}".format( self.pluginName )
    arg = ( DialogCatalogSettingRP.configQGIS, title, self.apiServer )
    self.mngRegisterQGis = ManagerRegisterQGis( *arg )

  def settingImages(self):
    CatalogImage.settingImages(self)
    dlg = DialogCatalogSettingRP( self.mainWindow, self.icon, self.settings )
    if dlg.exec_() == QtGui.QDialog.Accepted:
      self.settings = dlg.getData()
