from enum import Enum

class CaseUrgency(str, Enum):
    ELECTIVE = "Elective"
    URGENT = "Urgent"
    EMERGENCY = "Emergency"


class SurgeonTitle(str, Enum):
    CONSULTANT = "Consultant"
    REGISTRAR = "Registrar"
    SHO = "SHO"
    FELLOW = "Fellow"


class Anaesthetic(str, Enum):
    SPINAL = "Spinal"
    GENERAL = "General"
    NERVE_ROOT_BLOCK = "NerveRootBlock"
    SEDATION = "Sedation"
    LOCAL_ANAESTHETIC = "LocalAnaesthetic"


class Speciality(str, Enum):
    ORTHOPAEDICS = "Orthopaedics"
    GENERAL_SURGERY = "General Surgery"
    ENT = "ENT"
    UROLOGY = "Urology"
    UPPER_GI = "Upper GI"
    NEUROSURGERY = "Neurosurgery"
    CARDIOTHORACIC = "Cardiothoracic"
    PLASTICS = "Plastics"
    VASCULAR = "Vascular"
    GYNAECOLOGY = "Gynaecology"
    OPHTHALMOLOGY = "Ophthalmology"
    COLORECTAL = "Colorectal"


class PreferenceCategory(str, Enum):
    INSTRUMENTS = "Instruments"
    CONSUMABLES = "Consumables"
    POSITIONING = "Positioning"
    IMAGING = "Imaging"
    EQUIPMENT = "Equipment"
    DRUGS = "Drugs"
    SUTURES = "Sutures"
    DRESSINGS = "Dressings"
    IDIOSYNCRASIES = "Idiosyncrasies"
    DISPOSABLES = "Disposables"




