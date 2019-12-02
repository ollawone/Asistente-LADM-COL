# -*- coding: utf-8 -*-
"""
/***************************************************************************
                              Asistente LADM_COL
                             --------------------
        begin                : 2019-11-26
        git sha              : :%H$
        copyright            : (C) 2019 by Jhon Galindo (Incige SAS)
        email                : jhonsigpjc@gmail.com
 ***************************************************************************/
/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License v3.0 as          *
 *   published by the Free Software Foundation.                            *
 *                                                                         *
 ***************************************************************************/
"""
import os

from qgis.PyQt.QtWidgets import (QDialog,
                                 QMessageBox,
                                 QDialogButtonBox,
                                 QSizePolicy)
from qgis.PyQt.QtCore import (Qt,
                              QSettings,
                              QCoreApplication)
from qgis.PyQt.QtGui import  QValidator
from qgis.core import (Qgis,
                       QgsProject,
                       QgsWkbTypes,
                       QgsVectorLayer,
                       QgsProcessingFeedback,
                       QgsVectorLayerJoinInfo)
from qgis.gui import QgsMessageBar

import processing

from asistente_ladm_col.config.general_config import (BLO_LIS_FILE_PATH,
                                                      SETTINGS_CONNECTION_TAB_INDEX)

from asistente_ladm_col.config.table_mapping_config import Names
from asistente_ladm_col.config.general_config import LAYER
from asistente_ladm_col.config.enums import EnumDbActionType
from asistente_ladm_col.gui.dialogs.dlg_settings import SettingsDialog
from asistente_ladm_col.lib.logger import Logger
from asistente_ladm_col.utils.qt_utils import (OverrideCursor,
                                               FileValidator,
                                               DirValidator,
                                               Validators,
                                               make_file_selector,
                                               make_folder_selector)
from asistente_ladm_col.utils import get_ui_class

DIALOG_LOG_EXCEL_UI = get_ui_class('dialogs/dlg_etl_cobol.ui')

class CobolBaseDialog(QDialog, DIALOG_LOG_EXCEL_UI):
    def __init__(self, qgis_utils, db, conn_manager, parent=None):
        QDialog.__init__(self, parent)
        self.setupUi(self)
        self.qgis_utils = qgis_utils
        self._db = db
        self.conn_manager = conn_manager
        self.parent = parent
        self.logger = Logger()

        self.names = Names()
        self._db_was_changed = False  # To postpone calling refresh gui until we close this dialog instead of settings
        self._running_etl = False
        self.validators = Validators()
        self.initialize_feedback()

        self.buttonBox.accepted.disconnect()
        self.buttonBox.accepted.connect(self.accepted)
        self.buttonBox.button(QDialogButtonBox.Ok).setText(QCoreApplication.translate("ETLCobolDialog", "Import"))
        self.finished.connect(self.finished_slot)

        self._layers = dict()
        self.initialize_layers()

        self.btn_browse_file_blo.clicked.connect(
            make_file_selector(self.txt_file_path_blo, QCoreApplication.translate("ETLCobolDialog",
                        "Select the BLO .lis file with Cobol data "),
                        QCoreApplication.translate("ETLCobolDialog", 'lis File (*.lis)')))

        self.btn_browse_file_uni.clicked.connect(
            make_file_selector(self.txt_file_path_uni, QCoreApplication.translate("ETLCobolDialog",
                        "Select the UNI .lis file with Cobol data "),
                        QCoreApplication.translate("ETLCobolDialog", 'lis File (*.lis)')))

        self.btn_browse_file_ter.clicked.connect(
            make_file_selector(self.txt_file_path_ter, QCoreApplication.translate("ETLCobolDialog",
                        "Select the TER .lis file with Cobol data "),
                        QCoreApplication.translate("ETLCobolDialog", 'lis File (*.lis)')))

        self.btn_browse_file_pro.clicked.connect(
            make_file_selector(self.txt_file_path_pro, QCoreApplication.translate("ETLCobolDialog",
                        "Select the PRO .lis file with Cobol data "),
                        QCoreApplication.translate("ETLCobolDialog", 'lis File (*.lis)')))

        self.btn_browse_file_gdb.clicked.connect(
                make_folder_selector(self.txt_file_path_gdb, title=QCoreApplication.translate(
                'ETLCobolDialog', 'Open GDB folder'), parent=None))

        file_validator_blo = FileValidator(pattern='*.lis', allow_empty=True)
        file_validator_lis = FileValidator(pattern='*.lis', allow_non_existing=False)
        dir_validator_gdb = DirValidator(pattern='*.gdb', allow_non_existing=False)
       
        self.bar = QgsMessageBar()
        self.bar.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.layout().addWidget(self.bar, 0, 0, Qt.AlignTop)

        self.txt_file_path_blo.setValidator(file_validator_blo)
        self.txt_file_path_uni.setValidator(file_validator_lis)
        self.txt_file_path_ter.setValidator(file_validator_lis)
        self.txt_file_path_pro.setValidator(file_validator_lis)
        self.txt_file_path_gdb.setValidator(dir_validator_gdb)

        self.txt_file_path_blo.textChanged.connect(self.validators.validate_line_edits)
        self.txt_file_path_uni.textChanged.connect(self.validators.validate_line_edits)
        self.txt_file_path_ter.textChanged.connect(self.validators.validate_line_edits)
        self.txt_file_path_pro.textChanged.connect(self.validators.validate_line_edits)
        self.txt_file_path_gdb.textChanged.connect(self.validators.validate_line_edits)

        self.txt_file_path_blo.textChanged.connect(self.set_import_button_enabled)
        self.txt_file_path_uni.textChanged.connect(self.set_import_button_enabled)
        self.txt_file_path_ter.textChanged.connect(self.set_import_button_enabled)
        self.txt_file_path_pro.textChanged.connect(self.set_import_button_enabled)
        self.txt_file_path_gdb.textChanged.connect(self.set_import_button_enabled)

        # Trigger validations right now
        self.txt_file_path_uni.textChanged.emit(self.txt_file_path_uni.text())
        self.txt_file_path_ter.textChanged.emit(self.txt_file_path_ter.text())
        self.txt_file_path_pro.textChanged.emit(self.txt_file_path_pro.text())
        self.txt_file_path_gdb.textChanged.emit(self.txt_file_path_gdb.text())

    def progress_changed(self):
        QCoreApplication.processEvents()  # Listen to cancel from the user
        self.progress.setValue(self.feedback.progress())

    def initialize_layers(self):
        self._layers = {
            self.names.GC_PARCEL_T: {'name': self.names.GC_PARCEL_T, 'geometry': None, LAYER: None},
            self.names.GC_OWNER_T: {'name': self.names.GC_OWNER_T, 'geometry': None, LAYER: None},
            self.names.GC_ADDRESS_T: {'name': self.names.GC_ADDRESS_T, 'geometry': QgsWkbTypes.LineGeometry, LAYER: None},
            self.names.GC_BUILDING_UNIT_T: {'name': self.names.GC_BUILDING_UNIT_T, 'geometry': QgsWkbTypes.PolygonGeometry, LAYER: None},
            self.names.GC_BUILDING_T: {'name': self.names.GC_BUILDING_T, 'geometry': QgsWkbTypes.PolygonGeometry, LAYER: None},
            self.names.GC_PLOT_T: {'name': self.names.GC_PLOT_T, 'geometry': QgsWkbTypes.PolygonGeometry, LAYER: None},
            self.names.GC_RURAL_DIVISION_T: {'name': self.names.GC_RURAL_DIVISION_T, 'geometry': QgsWkbTypes.PolygonGeometry, LAYER: None},
            self.names.GC_URBAN_SECTOR_T: {'name': self.names.GC_URBAN_SECTOR_T, 'geometry': QgsWkbTypes.PolygonGeometry, LAYER: None},
            self.names.GC_RURAL_SECTOR_T: {'name': self.names.GC_RURAL_SECTOR_T, 'geometry': QgsWkbTypes.PolygonGeometry, LAYER: None},
            self.names.GC_PERIMETER_T: {'name': self.names.GC_PERIMETER_T, 'geometry': QgsWkbTypes.PolygonGeometry, LAYER: None},
            self.names.GC_BLOCK_T: {'name': self.names.GC_BLOCK_T, 'geometry': QgsWkbTypes.PolygonGeometry, LAYER: None},
            self.names.GC_NEIGHBOURHOOD_T: {'name': self.names.GC_NEIGHBOURHOOD_T, 'geometry': QgsWkbTypes.PolygonGeometry, LAYER: None},
            self.names.GC_COMMISSION_BUILDING_T: {'name': self.names.GC_COMMISSION_BUILDING_T, 'geometry': QgsWkbTypes.PolygonGeometry, LAYER: None},
            self.names.GC_COMMISSION_PLOT_T: {'name': self.names.GC_COMMISSION_PLOT_T, 'geometry': QgsWkbTypes.PolygonGeometry, LAYER: None},
            self.names.GC_COMMISSION_BUILDING_UNIT_T: {'name': self.names.GC_COMMISSION_BUILDING_UNIT_T, 'geometry': QgsWkbTypes.PolygonGeometry, LAYER: None},
        }

    def reject(self):
        if self._running_etl:
            reply = QMessageBox.question(self,
                    QCoreApplication.translate("ETLCobolDialog", "Warning"),
                    QCoreApplication.translate("ETLCobolDialog","The ETL Cobol is still running. Do you want to cancel it? If you cancel, the data might be incomplete in the target database."),
                    QMessageBox.Yes, QMessageBox.No)
        
            if reply == QMessageBox.Yes:
                self.feedback.cancel()
                self._running_etl = False
                self.logger.info(__name__, "ETL-Cobol cancelled!")
        else:
            if self._db_was_changed:
                self.conn_manager.db_connection_changed.emit(self._db, self._db.test_connection()[0])
            self.logger.info(__name__, "Dialog closed.")
            self.done(1)

    def finished_slot(self, result):
        self.bar.clearWidgets()

    def set_import_button_enabled(self):
        if self.txt_file_path_blo.isVisible():
            state_blo = self.txt_file_path_blo.validator().validate(self.txt_file_path_blo.text().strip(), 0)[0]
        else:
            state_blo = QValidator.Acceptable

        if self.txt_file_path_uni.isVisible():    
            state_uni = self.txt_file_path_uni.validator().validate(self.txt_file_path_uni.text().strip(), 0)[0]
        else:
            state_uni = QValidator.Acceptable

        if self.txt_file_path_ter.isVisible():    
            state_ter  = self.txt_file_path_ter.validator().validate(self.txt_file_path_ter.text().strip(), 0)[0]
        else:
            state_ter = QValidator.Acceptable

        if self.txt_file_path_pro.isVisible():    
            state_pro = self.txt_file_path_pro.validator().validate(self.txt_file_path_pro.text().strip(), 0)[0]
        else:
            state_pro = QValidator.Acceptable

        if self.txt_file_path_gdb.isVisible():    
            state_gdb = self.txt_file_path_gdb.validator().validate(self.txt_file_path_gdb.text().strip(), 0)[0]
        else:
            state_gdb = QValidator.Acceptable

        if self.target_data.objectName() == 'Form_missing_supplies_cobol':
            if self.target_data.txt_file_path_folder_supplies.isVisible():    
                state_folder = self.target_data.txt_file_path_folder_supplies.validator().validate(
                    self.target_data.txt_file_path_folder_supplies.text().strip(), 0)[0]
            else:
                state_folder = QValidator.Acceptable
        else:
            state_folder = QValidator.Acceptable

        if state_blo == QValidator.Acceptable and state_uni == QValidator.Acceptable and \
            state_ter == QValidator.Acceptable and state_pro == QValidator.Acceptable and \
            state_gdb == QValidator.Acceptable and state_folder == QValidator.Acceptable:
            self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(True)
        else:
             self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(False)

    def initialize_feedback(self):
        self.progress.setValue(0)
        self.progress.setVisible(False)
        self.feedback = QgsProcessingFeedback()         
        self.feedback.progressChanged.connect(self.progress_changed) 

    def db_connection_changed(self, db, ladm_col_db):
        # We dismiss parameters here, after all, we already have the db, and the ladm_col_db may change from this moment
        # until we close the supplies dialog (e.g., we might run an import schema before under the hood)
        self._db_was_changed = True

    def save_settings(self):
        settings = QSettings()
        settings.setValue('Asistente-LADM_COL/etl_cobol/blo_path', self.txt_file_path_blo.text())
        settings.setValue('Asistente-LADM_COL/etl_cobol/uni_path', self.txt_file_path_uni.text())
        settings.setValue('Asistente-LADM_COL/etl_cobol/ter_path', self.txt_file_path_ter.text())
        settings.setValue('Asistente-LADM_COL/etl_cobol/pro_path', self.txt_file_path_pro.text())
        settings.setValue('Asistente-LADM_COL/etl_cobol/gdb_path', self.txt_file_path_gdb.text())
        if self.target_data.objectName() == 'Form_missing_supplies_cobol':
            settings.setValue('Asistente-LADM_COL/etl_cobol/folder_path', self.target_data.txt_file_path_folder_supplies.text())

    def restore_settings(self):
        settings = QSettings()
        self.txt_file_path_blo.setText(settings.value('Asistente-LADM_COL/etl_cobol/blo_path', ''))
        self.txt_file_path_uni.setText(settings.value('Asistente-LADM_COL/etl_cobol/uni_path', ''))
        self.txt_file_path_ter.setText(settings.value('Asistente-LADM_COL/etl_cobol/ter_path', ''))
        self.txt_file_path_pro.setText(settings.value('Asistente-LADM_COL/etl_cobol/pro_path', ''))
        self.txt_file_path_gdb.setText(settings.value('Asistente-LADM_COL/etl_cobol/gdb_path', ''))

        if self.target_data.objectName() == 'Form_missing_supplies_cobol':
            self.target_data.txt_file_path_folder_supplies.setText(settings.value('Asistente-LADM_COL/etl_cobol/folder_path', ' '))

    def load_lis_files(self, lis_paths):
        self.lis_paths = lis_paths

        root = QgsProject.instance().layerTreeRoot()
        lis_group = root.addGroup(QCoreApplication.translate("ETLCobolDialog", "LIS Supplies"))

        for name in self.lis_paths:
            uri = 'file:///{}?type=csv&delimiter=;&detectTypes=yes&geomType=none&subsetIndex=no&watchFile=no'.format(self.lis_paths[name])
            layer = QgsVectorLayer(uri, name, 'delimitedtext')
            if layer.isValid():
                self.lis_paths[name] = layer
                QgsProject.instance().addMapLayer(layer, False)
                lis_group.addLayer(layer)
            else:
                if name == 'blo':
                    # BLO is kind of optional, if it is not given, we pass a default one
                    uri = 'file:///{}?type=csv&delimiter=;&detectTypes=yes&geomType=none&subsetIndex=no&watchFile=no'.format(BLO_LIS_FILE_PATH)
                    layer = QgsVectorLayer(uri, name, 'delimitedtext')
                    self.lis_paths[name] = layer
                    QgsProject.instance().addMapLayer(layer, False)
                    lis_group.addLayer(layer)
                else:
                    return False, QCoreApplication.translate("ETLCobolDialog", "There were troubles loading the LIS file called '{}'.".format(name))

        return True, ''

    def load_gdb_files(self, required_layers):
        self.gdb_paths = {}

        gdb_path = self.txt_file_path_gdb.text()
        layer = QgsVectorLayer(gdb_path, 'layer name', 'ogr')

        if not layer.isValid():
            return False, QCoreApplication.translate("ETLCobolDialog", "There were troubles loading the GDB.")

        sublayers = layer.dataProvider().subLayers()

        root = QgsProject.instance().layerTreeRoot()
        gdb_group = root.addGroup(QCoreApplication.translate("ETLCobolDialog", "GDB Supplies"))

        for data in sublayers:
            sublayer = data.split('!!::!!')[1]
            if sublayer in required_layers:
                layer = QgsVectorLayer(gdb_path + '|layername=' + sublayer, sublayer, 'ogr')
                self.gdb_paths[sublayer] = layer
                QgsProject.instance().addMapLayer(layer, False)
                gdb_group.addLayer(layer)

        if len(self.gdb_paths) != len(required_layers):
            return False, QCoreApplication.translate("ETLCobolDialog", "The GDB does not have the required layers!")

        return True, ''

    def load_model_layers(self):
        self.qgis_utils.get_layers(self._db, self._layers, load=True)
        if not self._layers:
            return False, QCoreApplication.translate("ETLCobolDialog",
                                                     "There was a problem loading layers from the 'Supplies' model!")

        return True, ''

    def show_message(self, message, level):
        self.bar.clearWidgets()  # Remove previous messages before showing a new one
        self.bar.pushMessage(message, level, 15)