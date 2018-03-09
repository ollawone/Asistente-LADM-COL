# -*- coding: utf-8 -*-
"""
/***************************************************************************
                              Asistente LADM_COL
                             --------------------
        begin                : 2018-03-06
        git sha              : :%H$
        copyright            : (C) 2018 by Sergio Ramírez (Incige SAS)
        email                : seralra96@gmail.com
 ***************************************************************************/
/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License v3.0 as          *
 *   published by the Free Software Foundation.                            *
 *                                                                         *
 ***************************************************************************/
"""
from qgis.core import QgsEditFormConfig, QgsVectorLayerUtils, Qgis, QgsWkbTypes
from qgis.gui import QgsMessageBar
from qgis.PyQt.QtCore import Qt, QPoint, QCoreApplication
from qgis.PyQt.QtWidgets import QAction, QWizard


from ..utils import get_ui_class
#from ..utils.qt_utils import enable_next_wizard, disable_next_wizard
from ..config.table_mapping_config import (
    RESPONSIBILITY_TABLE,
    RESPONSIBILITY_TYPE_TABLE,
    NATURAL_PARTY_TABLE,
    LEGAL_PARTY_TABLE,
    PARCEL_TABLE,
    LA_BAUNIT_TABLE,
    LA_GROUP_PARTY_TABLE,
    VIDA_UTIL_FIELD_BOUNDARY_TABLE
)

WIZARD_UI = get_ui_class('wiz_create_responsibility_cadastre.ui')

class CreateResponsibilityCadastreWizard(QWizard, WIZARD_UI):
    def __init__(self, iface, db, qgis_utils, parent=None):
        QWizard.__init__(self, parent)
        self.setupUi(self)
        self.iface = iface
        self._plot_layer = None
        self._db = db
        self.qgis_utils = qgis_utils


        self.button(QWizard.FinishButton).clicked.connect(self.prepare_responsibility_creation)

    def prepare_responsibility_creation(self):
        # Load layers
        res_layers = self.qgis_utils.get_layers(self._db, {
            RESPONSIBILITY_TABLE: {'name':RESPONSIBILITY_TABLE, 'geometry':None},
            RESPONSIBILITY_TYPE_TABLE: {'name':RESPONSIBILITY_TYPE_TABLE, 'geometry':None},
            NATURAL_PARTY_TABLE: {'name':NATURAL_PARTY_TABLE, 'geometry':None},
            LEGAL_PARTY_TABLE:{'name':LEGAL_PARTY_TABLE, 'geometry':None},
            PARCEL_TABLE:{'name':PARCEL_TABLE, 'geometry':None},
            LA_BAUNIT_TABLE:{'name':LA_BAUNIT_TABLE, 'geometry':None},
            LA_GROUP_PARTY_TABLE:{'name':LA_GROUP_PARTY_TABLE, 'geometry':None}}, load=True)

        self._responsibility_layer = res_layers[RESPONSIBILITY_TABLE]
        if self._responsibility_layer is None:
            self.iface.messageBar().pushMessage("Asistente LADM_COL",
                QCoreApplication.translate("CreateResponsibilityCadastreWizard",
                                           "Responsibility layer couldn't be found..."),
                Qgis.Warning)
            return

        self._natural_party_layer = res_layers[NATURAL_PARTY_TABLE]
        if self._natural_party_layer is None:
            self.iface.messageBar().pushMessage("Asistente LADM_COL",
                QCoreApplication.translate("CreateResponsibilityCadastreWizard",
                                           "Natural Party layer couldn't be found..."),
                Qgis.Warning)
            return

        self._legal_party_layer = res_layers[LEGAL_PARTY_TABLE]
        if self._legal_party_layer is None:
            self.iface.messageBar().pushMessage("Asistente LADM_COL",
                QCoreApplication.translate("CreateResponsibilityCadastreWizard",
                                           "Legal Party layer couldn't be found..."),
                Qgis.Warning)
            return

        self._parcel_layer = res_layers[PARCEL_TABLE]
        if self._parcel_layer is None:
            self.iface.messageBar().pushMessage("Asistente LADM_COL",
                QCoreApplication.translate("CreateResponsibilityCadastreWizard",
                                           "Parcel layer couldn't be found..."),
                Qgis.Warning)
            return

        self._la_baunit_layer = res_layers[LA_BAUNIT_TABLE]
        if self._la_baunit_layer is None:
            self.iface.messageBar().pushMessage("Asistente LADM_COL",
                QCoreApplication.translate("CreateResponsibilityCadastreWizard",
                                           "LA_Baunit layer couldn't be found..."),
                Qgis.Warning)
            return

        self._la_group_party_layer = res_layers[LA_GROUP_PARTY_TABLE]
        if self._la_group_party_layer is None:
            self.iface.messageBar().pushMessage("Asistente LADM_COL",
                QCoreApplication.translate("CreateResponsibilityCadastreWizard",
                                           "LA_Group Party layer couldn't be found..."),
                Qgis.Warning)
            return

        # Configure automatic fields
        self.qgis_utils.configureAutomaticField(self._responsibility_layer, VIDA_UTIL_FIELD_BOUNDARY_TABLE, "now()")

        # Configure relation fields
        self._natural_party_layer.setDisplayExpression('"documento_identidad"+\' \'+"primer_apellido"+\' \'+"segundo_apellido"+\' \'+"primer_nombre"+\' \'+"segundo_nombre"')
        self._legal_party_layer.setDisplayExpression('"numero_nit"+\' \'+"razon_social"')
        self._parcel_layer.setDisplayExpression('"nupre"+\' \'+"fmi"+\' \'+"nombre"')
        self._la_baunit_layer.setDisplayExpression('"t_id"+\' \'+"nombre"+\' \'+"tipo"')
        self._la_group_party_layer.setDisplayExpression('"t_id"+\' \'+"nombre"')

        # Don't suppress (i.e., show) feature form
        form_config = self._responsibility_layer.editFormConfig()
        form_config.setSuppress(QgsEditFormConfig.SuppressOff)
        self._responsibility_layer.setEditFormConfig(form_config)

        self.edit_spatial_source()

    def edit_spatial_source(self):
        # Open Form
        self.iface.layerTreeView().setCurrentLayer(self._responsibility_layer)
        self._responsibility_layer.startEditing()
        self.iface.actionAddFeature().trigger()
