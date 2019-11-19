# -*- coding: utf-8 -*-
"""
/***************************************************************************
                              Asistente LADM_COL
                             --------------------
        begin                : 2019-11-13
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
from qgis.core import (Qgis,
                       QgsProject,
                       QgsWkbTypes,
                       QgsVectorLayer,
                       QgsProcessingFeedback,
                       QgsVectorLayerJoinInfo)
from qgis.gui import QgsMessageBar

import processing

from ...config.general_config import (BLO_LIS_FILE_PATH,
                                      SETTINGS_CONNECTION_TAB_INDEX,
                                      SETTINGS_MODELS_TAB_INDEX)

from ...config.enums import EnumDbActionType
from ...utils.qt_utils import (OverrideCursor,
                               FileValidator)
from ...utils import get_ui_class
from ...gui.dialogs.dlg_settings import SettingsDialog

from asistente_ladm_col.utils.qt_utils import (make_file_selector,
                                               make_folder_selector)
from asistente_ladm_col.config.table_mapping_config import Names
from asistente_ladm_col.config.general_config import LAYER

DIALOG_LOG_EXCEL_UI = get_ui_class('dialogs/dlg_etl_cobol.ui')


class ETLCobolDialog(QDialog, DIALOG_LOG_EXCEL_UI):
    def __init__(self, qgis_utils, db, conn_manager, parent=None):
        QDialog.__init__(self, parent)
        self.setupUi(self)
        self.qgis_utils = qgis_utils
        self._db = db
        self.conn_manager = conn_manager

        self.names = Names()
        self._db_was_changed = True
        self._running_etl = False
        self._validate_files = False
        self.feedback = QgsProcessingFeedback()
        self.feedback.progressChanged.connect(self.progress_changed)
        self.progress.setVisible(False)

        self.buttonBox.accepted.disconnect()
        self.buttonBox.rejected.disconnect()
        self.buttonBox.accepted.connect(self.accepted)
        self.buttonBox.button(QDialogButtonBox.Ok).setText(QCoreApplication.translate("ETLCobolDialog", "Import"))
        self.buttonBox.rejected.connect(self.close_dialog)
        self.finished.connect(self.finished_slot)

        self.btn_browse_connection.clicked.connect(self.show_settings)
        self.update_connection_info()

        self._layers = dict()
        self.initialize_layers()

        self.restore_settings()

        self.btn_browse_file_blo.clicked.connect(
            make_file_selector(self.txt_file_path_blo, QCoreApplication.translate("DialogExportData",
                        "Select the BLO .lis file with Cobol data "),
                        QCoreApplication.translate("DialogExportData", 'lis File (*.lis)')))

        self.btn_browse_file_uni.clicked.connect(
            make_file_selector(self.txt_file_path_uni, QCoreApplication.translate("DialogExportData",
                        "Select the UNI .lis file with Cobol data "),
                        QCoreApplication.translate("DialogExportData", 'lis File (*.lis)')))

        self.btn_browse_file_ter.clicked.connect(
            make_file_selector(self.txt_file_path_ter, QCoreApplication.translate("DialogExportData",
                        "Select the TER .lis file with Cobol data "),
                        QCoreApplication.translate("DialogExportData", 'lis File (*.lis)')))

        self.btn_browse_file_pro.clicked.connect(
            make_file_selector(self.txt_file_path_pro, QCoreApplication.translate("DialogExportData",
                        "Select the PRO .lis file with Cobol data "),
                        QCoreApplication.translate("DialogExportData", 'lis File (*.lis)')))

        self.btn_browse_file_gdb.clicked.connect(
                make_folder_selector(self.txt_file_path_gdb, title=QCoreApplication.translate(
                'SettingsDialog', 'Open GDB folder'), parent=None))

        fileValidator_lis = FileValidator(pattern=['*.lis'], allow_non_existing=False)
        fileValidator_gdb = FileValidator(pattern=['*.gdb'], allow_non_existing=False)

        self.txt_file_path_uni.setValidator(fileValidator_lis)
        self.txt_file_path_ter.setValidator(fileValidator_lis)
        self.txt_file_path_pro.setValidator(fileValidator_lis)
        self.txt_file_path_gdb.setValidator(fileValidator_gdb)

        self.txt_file_path_uni.textChanged.connect(self.validate_lis)
        self.txt_file_path_ter.textChanged.connect(self.validate_lis)
        self.txt_file_path_pro.textChanged.connect(self.validate_lis)
        self.txt_file_path_gdb.textChanged.connect(self.validate_gdb)

        self.txt_file_path_uni.textChanged.emit(self.txt_file_path_uni.text())
        self.txt_file_path_ter.textChanged.emit(self.txt_file_path_ter.text())
        self.txt_file_path_pro.textChanged.emit(self.txt_file_path_pro.text())
        self.txt_file_path_gdb.textChanged.emit(self.txt_file_path_gdb.text())
        
        self.bar = QgsMessageBar()
        self.bar.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.layout().addWidget(self.bar, 0, 0, Qt.AlignTop)

        # TODO; Set validators

    def progress_changed(self):
        self.progress.setValue(self.feedback.progress())

    def validate_lis(self):
        extension = '.lis'
        status = 0
        labels = [self.txt_file_path_uni,
                 self.txt_file_path_ter,
                 self.txt_file_path_pro]

        for label in labels:
            if not os.path.isfile(label.text().strip()):
                label.setStyleSheet('QLineEdit {{ background-color: {} }}'.format('#ffd356'))
                status = status + 1
            elif os.path.splitext(label.text().strip())[1] != extension:
                label.setStyleSheet('QLineEdit {{ background-color: {} }}'.format('#ffd356'))
                status = status + 1
            else:
                label.setStyleSheet('QLineEdit {{ background-color: {} }}'.format('#fff'))

        if status > 0:
            self.buttonBox.button(QDialogButtonBox.Ok).setDisabled(True)
            self._validate_files = False
        else:
            self.buttonBox.button(QDialogButtonBox.Ok).setDisabled(False)
            self._validate_files = True

    def validate_gdb(self):
        extension = '.gdb'
        label = self.txt_file_path_gdb

        if not os.path.isdir(label.text().strip()):
            label.setStyleSheet('QLineEdit {{ background-color: {} }}'.format('#ffd356'))
            self.buttonBox.button(QDialogButtonBox.Ok).setDisabled(True)
        elif os.path.splitext(label.text().strip())[1] != extension:
            label.setStyleSheet('QLineEdit {{ background-color: {} }}'.format('#ffd356'))
            self.buttonBox.button(QDialogButtonBox.Ok).setDisabled(True)
        else:
            label.setStyleSheet('QLineEdit {{ background-color: {} }}'.format('#fff'))
            if self._validate_files:
                self.buttonBox.button(QDialogButtonBox.Ok).setDisabled(False)

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

    def accepted(self):
        self.save_settings()

        if self._db.test_connection()[0]:
            reply = QMessageBox.question(self,
                QCoreApplication.translate("ETLCobolDialog", "Warning"),
                QCoreApplication.translate("ETLCobolDialog","The schema <i>{schema}</i> already has a valid LADM_COL structure.<br/><br/>If such schema has any data, loading data into it might cause invalid data.<br/><br/>Do you still want to continue?".format(schema=self._db.schema)),
                QMessageBox.Yes, QMessageBox.No)

            if reply == QMessageBox.Yes:
                with OverrideCursor(Qt.WaitCursor):
                    res_lis, msg_lis = self.load_lis_files()
                    if res_lis:
                        res_gdb, msg_gdb = self.load_gdb_files()
                        if res_gdb:
                            res_model, msg_model = self.load_model_layers()
                            if res_model:
                                self._running_etl = True
                                self.run_model_etl_cobol()
                                if not self.feedback.isCanceled():
                                    self.progress.setValue(100)
                                    self.buttonBox.clear()
                                    self.buttonBox.setEnabled(True)
                                    self.buttonBox.addButton(QDialogButtonBox.Close)                
                                self._running_etl = False
                            else:
                                self.show_message(msg_model, Qgis.Warning)
                        else:
                            self.show_message(msg_gdb, Qgis.Warning)
                    else:
                        self.show_message(msg_lis, Qgis.Warning)
        else:
            with OverrideCursor(Qt.WaitCursor):
                # TODO: if an empty schema was selected, do the magic under the hood
                # self.create_model_into_database()
                # Now execute "accepted()"
                pass

    def close_dialog(self):
        if self._running_etl:
            reply = QMessageBox.question(self,
                    QCoreApplication.translate("ETLCobolDialog", "Warning"),
                    QCoreApplication.translate("ETLCobolDialog","The ETL Cobol is still running. Do you want to cancel it? If you cancel, the data might be incomplete."),
                    QMessageBox.Yes, QMessageBox.No)
        
            if reply == QMessageBox.Yes:
                self.feedback.cancel()
                self._running_etl = False
                self.close()
        else:
            self.close()

    def finished_slot(self, result):
        self.bar.clearWidgets()

    def show_settings(self):
        dlg = SettingsDialog(qgis_utils=self.qgis_utils, conn_manager=self.conn_manager)

        dlg.db_connection_changed.connect(self.db_connection_changed)
        dlg.db_connection_changed.connect(self.qgis_utils.cache_layers_and_relations)

        # We only need those tabs related to Model Baker/ili2db operations
        for i in reversed(range(dlg.tabWidget.count())):
            if i not in [SETTINGS_CONNECTION_TAB_INDEX]:
                dlg.tabWidget.removeTab(i)

        dlg.set_action_type(EnumDbActionType.SCHEMA_IMPORT)

        if dlg.exec_():
            self._db = dlg.get_db_connection()
            self.update_connection_info()

    def db_connection_changed(self, db, ladm_col_db):
        self._db_was_changed = True

    def update_connection_info(self):
        db_description = self._db.get_description_conn_string()
        if db_description:
            self.db_connect_label.setText(db_description)
            self.db_connect_label.setToolTip(self._db.get_display_conn_string())
        else:
            self.db_connect_label.setText(
                QCoreApplication.translate("DialogExportData", "The database is not defined!"))
            self.db_connect_label.setToolTip('')

    def save_settings(self):
        settings = QSettings()
        settings.setValue('Asistente-LADM_COL/etl_cobol/blo_path', self.txt_file_path_blo.text())
        settings.setValue('Asistente-LADM_COL/etl_cobol/uni_path', self.txt_file_path_uni.text())
        settings.setValue('Asistente-LADM_COL/etl_cobol/ter_path', self.txt_file_path_ter.text())
        settings.setValue('Asistente-LADM_COL/etl_cobol/pro_path', self.txt_file_path_pro.text())
        settings.setValue('Asistente-LADM_COL/etl_cobol/gdb_path', self.txt_file_path_gdb.text())

    def restore_settings(self):
        settings = QSettings()
        self.txt_file_path_blo.setText(settings.value('Asistente-LADM_COL/etl_cobol/blo_path', ''))
        self.txt_file_path_uni.setText(settings.value('Asistente-LADM_COL/etl_cobol/uni_path', ''))
        self.txt_file_path_ter.setText(settings.value('Asistente-LADM_COL/etl_cobol/ter_path', ''))
        self.txt_file_path_pro.setText(settings.value('Asistente-LADM_COL/etl_cobol/pro_path', ''))
        self.txt_file_path_gdb.setText(settings.value('Asistente-LADM_COL/etl_cobol/gdb_path', ''))

    def load_lis_files(self):
        self.lis_paths = {
            'blo': self.txt_file_path_blo.text().strip(),
            'uni': self.txt_file_path_uni.text().strip(),
            'ter': self.txt_file_path_ter.text().strip(),
            'pro': self.txt_file_path_pro.text().strip()
        }

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

    def load_gdb_files(self):
        self.gdb_paths = {}

        required_layers = ['R_TERRENO','U_TERRENO','R_SECTOR','U_SECTOR','R_VEREDA','U_MANZANA','U_BARRIO'
                            ,'R_CONSTRUCCION','U_CONSTRUCCION','U_UNIDAD','R_UNIDAD','U_NOMENCLATURA_DOMICILIARIA',
                            'R_NOMENCLATURA_DOMICILIARIA', 'U_PERIMETRO']

        gdb_path = self.txt_file_path_gdb.text()
        layer = QgsVectorLayer(gdb_path, 'layer name', 'ogr')
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
            msg = QCoreApplication.translate("ETLCobolDialog", "The GDB does not have the required layers!")
            return False, msg

        return True, ''

    def load_model_layers(self):
        self.qgis_utils.get_layers(self._db, self._layers, load=True)
        if not self._layers:
            msg = QCoreApplication.translate("ETLCobolDialog", "There was a problem loading layers from the 'Supplies' model!")
            return False, msg

        return True, ''

    def run_model_etl_cobol(self):
        self.progress.setVisible(True)
        processing.run("model:ETL-model-supplies", 
            {'barrio': self.gdb_paths['U_BARRIO'],
            'gcbarrio': self._layers[self.names.GC_NEIGHBOURHOOD_T][LAYER],
            'gccomisionconstruccion': self._layers[self.names.GC_COMMISSION_BUILDING_T][LAYER],
            'gccomisionterreno': self._layers[self.names.GC_COMMISSION_PLOT_T][LAYER],
            'gcconstruccion': self._layers[self.names.GC_BUILDING_T][LAYER],
            'gcdireccion': self._layers[self.names.GC_ADDRESS_T][LAYER],
            'gcmanzana': self._layers[self.names.GC_BLOCK_T][LAYER],
            'gcperimetro': self._layers[self.names.GC_PERIMETER_T][LAYER],
            'gcpropietario': self._layers[self.names.GC_OWNER_T][LAYER],
            'gcsector': self._layers[self.names.GC_RURAL_SECTOR_T][LAYER],
            'gcsectorurbano': self._layers[self.names.GC_URBAN_SECTOR_T][LAYER],
            'gcterreno': self._layers[self.names.GC_PLOT_T][LAYER],
            'gcunidad': self._layers[self.names.GC_BUILDING_UNIT_T][LAYER],
            'gcunidadconstruccioncomision': self._layers[self.names.GC_COMMISSION_BUILDING_UNIT_T][LAYER],
            'gcvereda': self._layers[self.names.GC_RURAL_DIVISION_T][LAYER],
            'inputblo': self.lis_paths['blo'],
            'inputconstruccion': self.gdb_paths['R_CONSTRUCCION'],
            'inputmanzana': self.gdb_paths['U_MANZANA'],
            'inputperimetro': self.gdb_paths['U_PERIMETRO'],
            'inputpro': self.lis_paths['pro'],
            'inputrunidad': self.gdb_paths['R_UNIDAD'],
            'inputsector': self.gdb_paths['R_SECTOR'],
            'inputter': self.lis_paths['ter'],
            'inputterreno': self.gdb_paths['R_TERRENO'],
            'inputuconstruccion': self.gdb_paths['U_CONSTRUCCION'],
            'inputuni': self.lis_paths['uni'],
            'inputusector': self.gdb_paths['U_SECTOR'],
            'inpututerreno': self.gdb_paths['U_TERRENO'],
            'inputuunidad': self.gdb_paths['U_UNIDAD'],
            'inputvereda': self.gdb_paths['R_VEREDA'],
            'ouputlayer': self._layers[self.names.GC_PARCEL_T][LAYER],
            'rnomenclatura': self.gdb_paths['R_NOMENCLATURA_DOMICILIARIA'],
            'unomenclatura': self.gdb_paths['U_NOMENCLATURA_DOMICILIARIA']},
            feedback=self.feedback)

    def show_message(self, message, level):
        self.bar.clearWidgets()  # Remove previous messages before showing a new one
        self.bar.pushMessage(message, level, 15)