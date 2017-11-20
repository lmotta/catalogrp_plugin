#!/bin/bash
plugin_dir=$( basename $( pwd ) )
if [ -f "./"$plugin_dir".zip" ]; then
  rm "./"$plugin_dir".zip"
fi
mkdir "./"$plugin_dir
cp *.py "./$plugin_dir"
cp -R ./utils_catalog "./$plugin_dir"
for item in metadata.txt README.md LICENSE *.svg; do cp "./$item" "./$plugin_dir"; done
cd  "./"$plugin_dir"/utils_catalog"
rm *.pyc .directory
cd -
zip -r $plugin_dir $plugin_dir
rm -r $plugin_dir
#
kdialog --msgbox "Zip file created: "$plugin_dir".zip"
