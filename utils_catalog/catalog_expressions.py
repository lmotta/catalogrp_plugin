"""
/***************************************************************************
Name                 : Catalog expressions
Description          : Set of expressions for QGIS ( 2.8 or above )
Date                 : November, 2019.
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

from qgis.core import ( qgsfunction )
from apicatalog import API_Catalog 

@qgsfunction(args=1, group='Catalog TMS')
def getValueFromMetadata(values, feature, parent):
  """
  <h4>Return</h4>Get value of key of  'meta_json' field
  <p><h4>Syntax</h4>getValueFromMetadata('list_keys')</p>
  <p><h4>Argument</h4>list_keys -> String with a sequence of keys names - '"key1","key2",...'</p>
  <p><h4>Example</h4>getValueFromMetadata( '"key"' )</p><p>Return: Value of key</p>
  """
  if values[0].count('"') % 2 != 0:
    raise Exception("Catalog: Error! Key need double quotes: %s." % values[0] )
  
  if len( values[0] ) < 1:
    raise Exception("Catalog: Error! Field is empty." )
    

  name_metadata_json = 'meta_json'
  id_metadata_json = feature.fieldNameIndex( name_metadata_json )
  if id_metadata_json == -1:
    raise Exception("Catalog: Error! Need have '%s' field." % name_metadata_json )

  lstKey = map( lambda item: item.strip(), values[ 0 ].split(",") )
  lstKey = map( lambda item: item.strip('"'), lstKey )

  metadata_json = feature.attributes()[ id_metadata_json ] 
  try:
    ( success, valueKey) = API_Catalog.getValue( metadata_json, lstKey )
    if not success:
      raise Exception( valueKey )
  except Exception as e:
    raise Exception( e.message )

  return valueKey
