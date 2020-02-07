from qgis.PyQt.QtCore import (QObject,
                              QCoreApplication)

from asistente_ladm_col.config.general_config import SUPPLIES_DB_SOURCE
from asistente_ladm_col.config.gui.common_keys import (ACTION_SCHEMA_IMPORT_SUPPLIES,
                                                       ACTION_RUN_ETL_COBOL,
                                                       ACTION_EXPORT_DATA_SUPPLIES,
                                                       ACTION_ST_UPLOAD_XTF)
from asistente_ladm_col.config.mapping_config import LADMNames
from asistente_ladm_col.utils.singleton import SingletonQObject

TASK_INTEGRATE_SUPPLIES = 1
TASK_GENERATE_CADASTRAL_SUPPLIES = 2
SLOT_NAME = "SLOT_NAME"
SLOT_PARAMS = "SLOT_PARAMS"
STEP_NUMBER = "STEP_NUMBER"
STEP_NAME = "STEP_NAME"
STEP_DESCRIPTION = "STEP_DESCRIPTION"
STEP_ACTION = "STEP_ACTION"
STEP_CUSTOM_ACTION_SLOT = "STEP_CUSTOM_ACTION_SLOT"


class TaskStepsConfig(QObject, metaclass=SingletonQObject):
    def __init__(self):
        QObject.__init__(self)

        self._slot_caller = None
        self._steps_config = dict()

    def set_slot_caller(self, slot_caller):
        self._slot_caller = slot_caller

    def _initialize_config(self):
        self._steps_config = {
            TASK_GENERATE_CADASTRAL_SUPPLIES: {
                1: {STEP_NAME: QCoreApplication.translate("TaskStepsConfig", "Create supplies structure in DB"),
                    STEP_ACTION: ACTION_SCHEMA_IMPORT_SUPPLIES,
                    STEP_DESCRIPTION: "",
                    STEP_CUSTOM_ACTION_SLOT: {
                        SLOT_NAME: self._slot_caller.show_dlg_import_schema,
                        SLOT_PARAMS: {'db_source': SUPPLIES_DB_SOURCE,
                                      'selected_models': [LADMNames.SUPPORTED_SUPPLIES_MODEL]}}
                    },
                2: {STEP_NAME: QCoreApplication.translate("TaskStepsConfig", "Run supplies ETL"),
                    STEP_ACTION: ACTION_RUN_ETL_COBOL,
                    STEP_DESCRIPTION: ""
                    },
                3: {STEP_NAME: QCoreApplication.translate("TaskStepsConfig", "Generate XTF"),
                    STEP_ACTION: ACTION_EXPORT_DATA_SUPPLIES,
                    STEP_DESCRIPTION: ""
                    },
                4: {STEP_NAME: QCoreApplication.translate("TaskStepsConfig", "Upload XTF"),
                    STEP_ACTION: ACTION_ST_UPLOAD_XTF,
                    STEP_DESCRIPTION: ""
                    }
            },
            TASK_INTEGRATE_SUPPLIES: {
                1: {STEP_NAME: QCoreApplication.translate("TaskStepsConfig", "Connect to remote DB"),
                    STEP_ACTION: ACTION_SCHEMA_IMPORT_SUPPLIES,
                    STEP_DESCRIPTION: ""},
                2: {STEP_NAME: QCoreApplication.translate("TaskStepsConfig",
                                                          "Explore data from Cadastre and Land Registry"),
                    STEP_ACTION: ACTION_RUN_ETL_COBOL,
                    STEP_DESCRIPTION: ""
                    },
                3: {STEP_NAME: QCoreApplication.translate("TaskStepsConfig", "Start assisted integration"),
                    STEP_ACTION: ACTION_EXPORT_DATA_SUPPLIES,
                    STEP_DESCRIPTION: ""
                    }
            }
        }

    def _get_config(self):
        if not self._steps_config:
            self._initialize_config()

        return self._steps_config

    def get_steps_data(self, task_type):
        steps_data = list()
        if task_type in self._get_config():
            for id, data in self._get_config()[task_type].items():
                step_data = dict()
                step_data[STEP_NUMBER] = id
                step_data[STEP_NAME] = data[STEP_NAME]
                step_data[STEP_ACTION] = data[STEP_ACTION]
                step_data[STEP_DESCRIPTION] = data[STEP_DESCRIPTION]
                if STEP_CUSTOM_ACTION_SLOT in data:
                    step_data[STEP_CUSTOM_ACTION_SLOT] = data[STEP_CUSTOM_ACTION_SLOT]
                steps_data.append(step_data)

        return steps_data
