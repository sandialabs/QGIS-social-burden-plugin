import warnings
import os
import numpy as np
import processing
import tempfile
from datetime import datetime

from qgis.core import QgsProject
from qgis.core import QgsVectorLayer
from qgis.core import QgsField
from qgis.core import QgsFeature
from qgis.core import NULL
from qgis.core import QgsProcessing
from qgis.core import QgsProcessingAlgorithm
from PyQt5.QtCore import QVariant
from qgis.PyQt.QtWidgets import QAction
from qgis.PyQt.QtWidgets import QFileDialog
from .social_burden_calculator_dialog import SocialBurdenCalculatorDialog


class QgsSBCalcDataBridge:
    def __init__(self):
        # information fields about the facilities layer
        self._facilitiesLayerData = None  # data in the facilities table
        self._facilitiesLayerName = None  # name of the facilities layer (str)
        self._facilitiesLayer = None  # the actual QgsVectorLayer layer
        self._facilitiesLayerFieldNames = (
            None  # names of the columns in the facilities table
        )
        self._facilitiesIndexFieldName = None  # name of the index column for facilities
        self._facilitiesLatField = None
        self._facilitiesLongField = None
        self._facilitiesSectorField = None
        self._facilityLatitudes = None  # data values, np 1-d array
        self._facilityLongitudes = None  # data values, np 1-d array
        self._facilitiesHaveLatLongs = None

        # information fields about the population layer
        self._populationLayerData = None  # data contained in the population layer
        self._populationLayer = None  # the QgsVectorLayer object
        self._populationLayerName = None  # name of the population layer (str)
        self._populationFieldNames = (
            None  # names of the columns in the population layer table
        )
        self._populationIndexFieldName = (
            None  # name of the index field for the population
        )
        self._populationIndexValues = None  # the indices of the population
        self._populationHasCentroids = (
            None  # whether the user specified centroid fields
        )
        self._populationCentroidLatField = None  # specified latitude field, if any
        self._populationCentroidLongField = None  # specified longitude field, if any
        self._populationPopulationFieldName = (
            None  # specified field for population counts
        )
        self._populationAttainFactorFieldName = None

        self._populationCentroidsLayer = None  # this is the _layer_ (QgsVectorLayer)
        # that contains the population centroids.
        self._populationCentroidLats = None  # latitude values of the centroids
        self._populationCentroidLongs = None  # longitude values of the centroids

        # sector to service layer information fields
        self._sectorToServiceLayerData = None  # data in the sector to service table
        self._sectorToServiceLayerName = (
            None  # name of the sector to service layer (str)
        )
        self._sectorToServiceLayer = None
        self._sectorToServiceSectorField = None  # sector field name
        self._sectorToServiceEpfField = None  # effort per foot field name
        self._sectorToServiceZdeField = None  # zero-distance effort field name

        self._serviceNames = None  # this is calculated when demanded by the getter based on the serviceLayer's fields ,
        # so there's no setter.

        # exclusion profile information fields
        self._exclusionLayerName = None
        self._exclusionLayer = None
        self._hasExclusionLayer = None
        self._SLReduction = None
        self._SLReductionArray = None  # is of shape ( num facilities, )

        # facility-service join layer fields
        self._facilityServiceLayer = None  # the QgsVectorLayer object
        self._facilityServiceLayerData = None  # will hold all the data for the info
        self._facilityServiceFieldNames = None  # the names of the fields in the layer

        # csv export fields
        self._exportToCsv = None
        self._perCapitaCsvOutputPath = None
        self._aggregatedCsvOutputPath = None

        # rencat export fields
        self._exportToRencat = None
        self._exportToRencatPath = None

        self._exportAsRencatOutput = None
        self._exportAsRencatOutputPath = None
        
        
        #export fields for the per-population-per-facility-per-service interim 
        # results. This is an easter egg and should NOT be set to True except by developer.
        self._saveFacilityLevelResults = False
        # self._perCapitaPerFacilityPerServiceTablePath = None #this is currently formed by deriving from other values

    def importDataFromDialog(self, dlg):
        """
        Uses a social burden calculator dialog
        box construct to populate the necessary fields.

        input: the dialog box object

        output: none

        side effects: populates the information ABOUT
        the fields and prepares the
        QgsSBCalcDataBridge object to provide
        data from the tables/layers
        """

        # import information about the population groups
        self.setPopulationLayerName(dlg.getPopulationLayerName())
        self.setPopulationHasCentroids(dlg.getPopulationHasCentroids())
        self.setPopulationLatField(dlg.getPopulationLatField())
        self.setPopulationLongField(dlg.getPopulationLongField())
        self.setPopulationIndexField(dlg.getPopulationIndexField())
        self.setPopulationPopulationField(dlg.getPopulationPopulationField())
        self.setPopulationAttainFactorField(dlg.getPopulationAttainFactorField())

        self.setPopulationLayer(
            QgsProject.instance().mapLayersByName(self.getPopulationLayerName())[0]
        )

        # import information about the facilities
        self.setFacilitiesLayerName(dlg.getFacilitiesLayerName())
        self.setFacilityIndexField(dlg.getFacilitiesIndexFieldName())
        self.setHasFacilityLatLongs(dlg.getFacilitiesHaveLatLongs())
        self.setFacilityLatField(dlg.getFacilitiesLatFieldName())
        self.setFacilityLongField(dlg.getFacilitiesLongFieldName())
        self.setFacilitySectorField(dlg.getFacilitiesSectorFieldName())

        # import information about the sector to service table
        self.setSectorToServiceLayerName(dlg.getSectorToServiceLayerName())

        self.setSectorToServiceSectorField(dlg.getSectorToServiceSectorField())
        self.setSectorToServiceEpfField(dlg.getSectorToServiceEffortPerFootField())
        self.setSectorToServiceZdeField(dlg.getSectorToServiceZeroDistanceEffortField())

        self.setSectorToServiceLayer(
            QgsProject.instance().mapLayersByName(self.getSectorToServiceLayerName())[0]
        )

        # import information about the exclusion layer
        self.setExclusionLayerName(dlg.getExclusionLayerName())
        self.setHasExclusionLayer(dlg.getHasExclusionProfile())
        self.setSLReduction(dlg.getExclusionServiceLevelReduction())

        # import information about the exports to files
        self.setExportToCsv(dlg.exportToCSV())
        self.setPerCapitaCsvOutputPath(dlg.getPerCapitaCsvOutputPath())
        self.setAggregatedCsvOutputPath(dlg.getAggregatedCsvOutputPath())

        self.setExportToRencat(dlg.exportToRencat())
        self.setRencatInputPath(dlg.getExportToRencatPath())

        self.setExportAsRencatOutput(dlg.exportAsRencatOutput())
        self.setExportAsRencatOutputPath(dlg.getExportAsRencatOutputPath())

    def _extractPointLocations(self, layer: QgsVectorLayer, whichgeom: str):
        """
        Helper function to extract the latitude and
        longitude geometries from a point layer

        inputs:
            layer:QgsVectorLayer: the layer of interest.

        If the geometry of the layer isn't
        single points, will raise TypeError.
        if the geometries somehow
        don't exist, will raise a ValueError.

        returns:
             tuple of numpy 1-d arrays, (latitudes, longitudes)

        whichgeom should be either "facilities" or "population centroids",
            for maximally useful error messages.
        """

        geometryList = [layer.getGeometry(i.id()) for i in layer.getFeatures()]

        # these should be points. If they're not points, fail with slightly less not-useful message.
        try:
            pointList = [i.asPoint() for i in geometryList]
        except TypeError:
            raise TypeError(
                "The locations for the %s layer somehow aren't single-point type."
                % whichgeom
            )
        except ValueError:
            raise ValueError("Somehow the %s' geometry is null." % whichgeom)

        pointsArray = np.array([(i.y(), i.x()) for i in pointList])
        return (pointsArray[:, 0], pointsArray[:, 1])

    def _extractDataFromLayer(self, layer: QgsVectorLayer):
        """
        Extracts all data from the provided layer.

        returns list of items. Each item in the list
            is a list containing all items in one row of the original array.
        """

        return [i.attributes() for i in layer.getFeatures()]

    def createPopulationCentroids(self):
        """
        Calculate centroids of user-input population block group polygons layer:
        If user has said to use the specified columns, rather than calculating centroids,
        the user's specified lat-long columns are used to make a layer instead.

        Also performs a CRS check on the resulting layer and provides a warning if the CRS
        is not geographic.
        """

        if self.getPopulationHasCentroids():  # if it has centroids.
            outputs_Centroids1 = processing.run(
                "native:createpointslayerfromtable",
                {
                    "INPUT": self.getPopulationLayerName(),
                    "YFIELD": self.getPopulationLatField(),
                    "XFIELD": self.getPopulationLongField(),
                    "TARGET_CRS": "ProjectCrs",
                    "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
                },
            )
        else:
            # this output layer has all the same fields as the original.
            outputs_Centroids1 = processing.run(
                "native:centroids",
                {
                    "ALL_PARTS": False,  # True creates issues if, for example, a given population group is divided into multiple non-continguous sections - think Hawaii.
                    "INPUT": self.getPopulationLayerName(),
                    "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
                },
            )

        self.setPopulationCentroidsLayer(outputs_Centroids1["OUTPUT"])
        if not self.getPopulationCentroidsLayer().crs().isGeographic():
            warnings.warn(
                "Population layer after creating centroids is not in a lat/long CRS, \
            so outputs of this program will likely be garbage."
            )

    def createFacilitiesAsPointsLayer(self):
        """
        If the facilities are a table and latlongs are specified, make a layer out of it.

        Also performs a check on the CRS of the resulting facilities layer and
        creates a warning if the layer does not have a geographic CRS.
        """
        if self.getHasFacilityLatLongs():
            facilityLayer = processing.run(
                "native:createpointslayerfromtable",
                {
                    "INPUT": self.getFacilitiesLayerName(),
                    "XFIELD": self.getFacilityLongField(),
                    "YFIELD": self.getFacilityLatField(),
                    "TARGET_CRS": "ProjectCrs",
                    "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
                },
            )["OUTPUT"]
        else:
            facilityLayer = self.getFacilitiesLayerName()
            facilityLayer = QgsProject.instance().mapLayersByName(facilityLayer)[0]

        self.setFacilitiesLayer(facilityLayer)
        if not self.getFacilitiesLayer().crs().isGeographic():
            warnings.warn(
                "Facilities layer coordinate reference system is not in a lat-long format \
            (if you defined your lat/longs manually, check your project CRS). \
            This means results of this program will likely be garbage."
            )

    def createSLReductionArray(self):
        if self.getHasExclusionLayer():
            #   Make sure that the geometry of the exclusion profile layer is correct - if it is,will have no effect.
            outputs_FixGeometries1 = processing.run(
                "native:fixgeometries",
                {
                    "INPUT": self.getExclusionLayerName(),
                    "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
                },
            )
            #

            # Intersect user-input facilities layer with post-processed geometry-fixed exclusion profile layer:
            #   Determines which facilities are affected by the exclusion profile.
            outputs_Intersection1 = processing.run(
                "native:intersection",
                {
                    "INPUT": self.getFacilitiesLayer(),
                    "INPUT_FIELDS": [""],
                    "OVERLAY": outputs_FixGeometries1["OUTPUT"],
                    "OVERLAY_FIELDS": [""],
                    "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
                },
            )

            # Convert multi-part output of facilities x exclusion profile intersection to single parts layer:
            #   QGIS logistics.
            outputs_MultiToSinglePart1 = processing.run(
                "native:multiparttosingleparts",
                {
                    "INPUT": outputs_Intersection1["OUTPUT"],
                    "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
                },
            )
            #
            # Use field calculator to assign user-input value of the exclusion profile reduction on service
            #         levels as new field in facility x exclusion profile point layer:
            #       Create new column of reduction of service level based on the exclusion profile.
            outputs_FieldCalculator0 = processing.run(
                "native:fieldcalculator",
                {
                    "FIELD_LENGTH": 3,
                    "FIELD_NAME": "SL_Reduce",
                    "FIELD_PRECISION": 0,
                    "FIELD_TYPE": 1,
                    "FORMULA": self.getSLReduction(),
                    "INPUT": outputs_MultiToSinglePart1["OUTPUT"],
                    "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
                },
            )
            #
            # Use extract by locatoin with disjoint (outside of) method to extract facilities from the input layer
            #         that do NOT fall within the boundaries of the exclusion profile layer.
            outputs_ExctractByLocation1 = processing.run(
                "native:extractbylocation",
                {
                    "INPUT": self.getFacilitiesLayer(),
                    "INTERSECT": outputs_FixGeometries1["OUTPUT"],
                    "PREDICATE": [2],  # disjoint
                    "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
                },
            )
            #
            # Use merge algorithm to combine the untouched facilities falling outside the
            #           exclusion layer (calculated
            #         by the Difference algorithm) with the reduction-adjusted facilities falling
            #           inside the exclusion layer
            #        (calculated by the intersect & field calculator steps above)
            outputs_Merge1 = processing.run(
                "qgis:mergevectorlayers",
                {
                    "LAYERS": [
                        outputs_ExctractByLocation1["OUTPUT"],
                        outputs_FieldCalculator0["OUTPUT"],
                    ],
                    "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
                },
            )
            #
            #  Use field calculator to overwrite NULLS in the SL_Reduce
            # field with zeros for the facilities which fell outside
            #         the exclusion profile and therefore did not have an SL_Reduce value assigned to them.
            # This completes the description of service level reduction for any facilities that
            # fall into the exclusion area.
            outputs_FacilitiesWithSLReduce = processing.run(
                "native:fieldcalculator",
                {
                    "FIELD_LENGTH": 3,
                    "FIELD_NAME": "SL_Reduce",
                    "FIELD_PRECISION": 0,
                    "FIELD_TYPE": 1,
                    "FORMULA": 'if("SL_Reduce" is null, 0, "SL_Reduce")',
                    "INPUT": outputs_Merge1["OUTPUT"],
                    "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
                },
            )

            sl_reduce_idx = (
                outputs_FacilitiesWithSLReduce["OUTPUT"]
                .fields()
                .indexFromName("SL_Reduce")
            )
            sl_reduce_rows = [
                i.attributes()
                for i in outputs_FacilitiesWithSLReduce["OUTPUT"].getFeatures()
            ]

            sl_reduce_array = np.array(
                [
                    i[sl_reduce_idx] if type(i[sl_reduce_idx]) != QVariant else 0.0
                    for i in sl_reduce_rows
                ]
            )

        else:  # there was no exclusion layer. All we're doing is creating a column
            # containing the service level reduction, and every element in it is 0.
            sl_reduce_array = np.zeros(self.getFacilitiesLayer().featureCount())
            # service level reduction array is of shape (num facilities,)

        self.setSLReductionArray(sl_reduce_array)

    def createFacilityServiceLayer(self):
        """
        creates and stores the facility-service join layer.
        """
        facility_service_join = processing.run(
            "native:joinattributestable",
            {
                "INPUT": self.getFacilitiesLayer(),
                "FIELD": self.getFacilitySectorField(),  # join field name in input 1
                "INPUT_2": self.getSectorToServiceLayer(),  # sector to service table, as layer
                "FIELD_2": self.getSectorToServiceSectorField(),  # join field in input 2
                # 'FIELDS_TO_COPY': , #fields from table 2 that should be retained; other fields are discarded
                "METHOD": 1,  # one-to-one matching rather than one-to-many
                "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
            },
        )
        self.setFacilityServiceLayer(facility_service_join["OUTPUT"])

    def importLayerFromBurdenTempFile(
        self, tmp: tempfile.NamedTemporaryFile, name: str
    ):
        """
        name: the desired name of the layer upon import
        tmp: tempfile.NamedTemporaryFile: the file to import as a layer
        """
        layer = QgsVectorLayer(f"file:///{tmp.name}", name, "delimitedtext")
        QgsProject.instance().addMapLayer(layer)

    # -------------GETTERS -------------------

    # -------facilities getters ----

    def getFacilityDataByFieldName(self, fieldname: str, expected_type="string"):
        """
        optional input: "expected type" (i.e. the expected type of items in the output)
            options are:
                'string' or str
                "numeric" or int or float (strings in the former case, types in the latter)
        The default is "string"
        if "str",no processing will be done to convert null values.
        if "numeric", Qgis-specific data types will be converted, i.e. nulls becomes 0s.

        returns:
            if expected_type is "string", will return a python list
            if expected_type is "numeric", returns a numpy array.

        """

        # find index of that field

        # first we make sure that there are population field names to check
        if self._facilitiesLayerFieldNames is None:
            lay = self.getFacilitiesLayer()
            self._facilitiesLayerFieldNames = [i for i in lay.fields().names()]
        try:
            idx = self._facilitiesLayerFieldNames.index(fieldname)
        except ValueError:
            raise ValueError("The facilities layer has no field named %s" % fieldname)

        # we now know that there is such a field in the population layer
        # and what its index is.
        if expected_type in ["str", "string"] or expected_type == str:
            return [i[idx] for i in self.getFacilitiesLayerData()]
        elif expected_type == "numeric" or expected_type in [int, float]:
            return np.array(
                [
                    i[idx] if type(i[idx]) != QVariant else 0.0
                    for i in self.getFacilitiesLayerData()
                ]
            )
        else: 
            raise ValueError(f"Unexpected requested return type in getFacilityDataByFieldName(): {expected_type}.")


    def getFacilitiesLayerData(self):
        if self._facilitiesLayerData is None:
            tmp = self._extractDataFromLayer(self.getFacilitiesLayer())
            self.setFacilitiesLayerData(tmp)
        return self._facilitiesLayerData

    def getFacilitiesLayer(self):
        return self._facilitiesLayer

    def getFacilitiesLayerName(self):
        return self._facilitiesLayerName

    def getFacilityLatitudes(self):
        """
        expected return: np 1-d array
        """

        if self._facilityLatitudes is None:
            lat, long = self._extractPointLocations(
                self.getFacilitiesLayer(), "facilities"
            )
            self.setFacilityLatitudes(lat)
            self.setFacilityLongitudes(long)
        return self._facilityLatitudes

    def getFacilityLongitudes(self):
        """
        expected return: np 1-d array
        """
        if self._facilityLongitudes is None:
            lat, long = self._extractPointLocations(
                self.getFacilitiesLayer(), "facilities"
            )
            self.setFacilityLatitudes(lat)
            self.setFacilityLongitudes(long)
        return self._facilityLongitudes

    def getFacilityIndexField(self):
        return self._facilitiesIndexFieldName

    def getHasFacilityLatLongs(self):
        return self._facilitiesHaveLatLongs

    def getFacilityLatField(self):
        return self._facilitiesLatField

    def getFacilityLongField(self):
        return self._facilitiesLongField

    def getFacilitySectorField(self):
        return self._facilitiesSectorField

    # -------population getters  ----

    def getPopulationDataByFieldName(self, fieldname: str, expected_type="string"):
        """
        optional input: "expected type" (i.e. of entries in the return items)
        options are:
            'string' or str
            "numeric" or int or float (strings in the former case, types in the latter)
        The default is "string"
        if "str",no processing will be done to convert null values.
        if "numeric", Qgis-specific data types will be converted, i.e. nulls becomes 0s.

        returns:
            if expected_type is "string", will return a python list
            if expected_type is "numeric", returns a numpy array.
        """
        # find index of that field

        # first we make sure that there are population field names to check
        if self._populationFieldNames is None:
            lay = self.getPopulationLayer()
            self._populationFieldNames = [i for i in lay.fields().names()]
        try:
            idx = self._populationFieldNames.index(fieldname)
        except ValueError:
            raise ValueError("The population layer has no field named %s" % fieldname)

        # we now know that there is such a field in the population layer
        # and what its index is.
        if expected_type == "str" or expected_type == str or expected_type=="string":
            return [i[idx] for i in self.getPopulationLayerData()]
        elif expected_type == "numeric" or expected_type in [int, float]:
            return np.array(
                [
                    i[idx] if type(i[idx]) != QVariant else 0.0
                    for i in self.getPopulationLayerData()
                ]
            )
        else: 
            raise ValueError(f"Unexpected requested return type in getPopulationDataByFieldName(): {expected_type}.")

    def getPopulationLayerName(self):
        return self._populationLayerName

    def getPopulationHasCentroids(self):
        return self._populationHasCentroids

    def getPopulationLatField(self):
        return self._populationCentroidLatField

    def getPopulationLongField(self):
        return self._populationCentroidLongField

    def getPopulationIndexField(self):
        return self._populationIndexFieldName

    def getPopulationPopulationField(self):
        return self._populationPopulationFieldName

    def getPopulationAttainFactorField(self):
        return self._populationAttainFactorFieldName

    def getPopulationCentroidsLayer(self):
        return self._populationCentroidsLayer

    def getPopulationLatitudes(self):
        """
        expected return: np 1-d array
        """
        if self._populationCentroidLats is None:
            lat, long = self._extractPointLocations(
                self.getPopulationCentroidsLayer(), "population centroids"
            )
            self.setPopulationLatitudes(lat)
            self.setPopulationLongitudes(long)
        return self._populationCentroidLats

    def getPopulationLongitudes(self):
        """
        expected return: np 1-d array
        """
        if self._populationCentroidLongs is None:
            lat, long = self._extractPointLocations(
                self.getPopulationCentroidsLayer(), "population centroids"
            )
            self.setPopulationLatitudes(lat)
            self.setPopulationLongitudes(long)
        return self._populationCentroidLongs

    def getPopulationLayerData(self):
        if self._populationLayerData is None:
            tmp = self._extractDataFromLayer(self.getPopulationLayer())
            self.setPopulationLayerData(tmp)
        return self._populationLayerData

    def getPopulationLayer(self):
        if self._populationLayer is None:
            self._populationLayer = QgsProject.instance().mapLayersByName(
                self.getPopulationLayerName
            )[0]
        return self._populationLayer

    def getPopulationTotalPopulation(self):
        return np.sum(
            self.getPopulationDataByFieldName(
                self.getPopulationPopulationField(), expected_type=int
            )
        )

    # -----facility service layer getters --

    def getFacilityServiceLayer(self):
        return self._facilityServiceLayer

    def getFacilityServiceLayerData(self):
        if self._facilityServiceLayerData is None:
            tmp = self._extractDataFromLayer(self.getFacilityServiceLayer())
            self.setFacilityServiceLayerData(tmp)
        return self._facilityServiceLayerData

    def getFacilityServiceServiceArray(self):
        """
        this provides the mapping from facilities to service levels.

        Returns a numpy array of shape (number of facilities, number of services)
        ordered in the same order as the facilities and ordered in the same number
        as the service names.
        """

        # these are the indices with the facilities' service levels
        service_column_indices = [
            self.getFacilityServiceLayer().fields().indexFromName(i)
            for i in self.getServiceNames()
        ]

        # assemble the info at these column indices into a numpy array
        service_array = np.array(
            [
                [
                    i[j] if type(i[j]) != QVariant else 0.0
                    for j in service_column_indices
                ]
                for i in self.getFacilityServiceLayerData()
            ]
        )
        return service_array

    def getFacilityServiceDataByFieldName(self, fieldname: str, expected_type="string"):
        """
        optional input: "expected type"
            options are:
                'string' or str
                "numeric" or int or float (strings in the former case, types in the latter)
            The default is "string"
            if "str",no processing will be done to convert null values.
            if "numeric", Qgis-specific data types will be converted, i.e. nulls becomes 0s.

        returns:
            if expected_type is "string", will return a python list
            if expected_type is "numeric", returns a numpy array.
        """

        # find index of that field

        # first we make sure that there are facility service field names to check
        if self._facilityServiceFieldNames is None:
            lay = self.getFacilityServiceLayer()
            self._facilityServiceFieldNames = [i for i in lay.fields().names()]
        try:
            idx = self._facilityServiceFieldNames.index(fieldname)
        except ValueError:
            raise ValueError(
                "The facility service layer has no field named %s" % fieldname
            )

        # we now know that there is such a field in the layer
        # and what its index is.
        if expected_type in ["str", "string"] or expected_type == str:
            return [i[idx] for i in self.getFacilityServiceLayerData()]
        elif expected_type == "numeric" or expected_type in [int, float]:
            return np.array(
                [
                    i[idx] if type(i[idx]) != QVariant else 0.0
                    for i in self.getFacilityServiceLayerData()
                ]
            )
        else: 
            raise ValueError(f"Unexpected expeted type in getFacilityServiceDataByFieldName(): {expected_type}.")

    # ------ sector to service table getters --------

    def getSectorToServiceLayerName(self):
        return self._sectorToServiceLayerName

    def getSectorToServiceSectorField(self):
        return self._sectorToServiceSectorField

    def getSectorToServiceLayer(self):
        return self._sectorToServiceLayer

    def getSectorToServiceEpfField(self):
        return self._sectorToServiceEpfField

    def getSectorToServiceZdeField(self):
        return self._sectorToServiceZdeField

    def getServiceNames(self):
        self._serviceNames = [
            i
            for i in self.getSectorToServiceLayer().fields().names()
            if i
            not in [
                self.getSectorToServiceSectorField(),
                self.getSectorToServiceEpfField(),
                self.getSectorToServiceZdeField(),
            ]
        ]
        return self._serviceNames

    def getSectorToServiceLayerData(self):
        if self._sectorToServiceLayerData is None:
            serviceLayer = self.getSectorToServiceLayer()
            self._sectorToServiceLayerData = [
                i.attributes() for i in serviceLayer.getFeatures()
            ]
        return self._sectorToServiceLayerData

    def getSectors(self):
        """
        Returns the list of sectors (e.g., grocery store)
        available in the sector to service mapping table.
        """
        sector_idx = (
            self.getSectorToServiceLayer()
            .fields()
            .indexFromName(self.getSectorToServiceSectorField())
        )
        return [i[sector_idx] for i in self.getSectorToServiceLayerData()]

    def getServiceFieldIndices(self):
        """
        Returns the list of _indices_ of
        the service columns in the sector to service mapping table.
        """
        return [
            idx
            for idx, i in enumerate(self.getSectorToServiceLayer().fields().names())
            if i
            not in [
                self.getSectorToServiceSectorField(),
                self.getSectorToServiceEpfField(),
                self.getSectorToServiceZdeField(),
            ]
        ]

    def getSectorToServiceArray(self):
        """
        This is a numpy array of the sector to service mapping
        values, ordered by sectors in the rows and
        services in the columns.
        """
        service_fields_index_list = self.getServiceFieldIndices()
        return np.array(
            [
                [
                    i[j] if type(i[j]) != QVariant else 0.0
                    for j in service_fields_index_list
                ]
                for i in self.getSectorToServiceLayerData()
            ]
        )

    # ------- exclusion profile getters ----

    def getExclusionLayerName(self):
        return self._exclusionLayerName

    def getExclusionLayer(self):
        return self._exclusionLayer

    def getHasExclusionLayer(self):
        return self._hasExclusionLayer

    def getSLReduction(self):
        return self._SLReduction

    def getSLReductionArray(self):
        return self._SLReductionArray

    # -------- export getters -----

    def getExportToCsv(self):
        return self._exportToCsv

    def getPerCapitaCsvOutputPath(self):
        return self._perCapitaCsvOutputPath

    def getAggregatedCsvOutputPath(self):
        return self._aggregatedCsvOutputPath

    def getExportToRencat(self):
        return self._exportToRencat

    def getRencatInputPath(self):
        return self._exportToRencatPath

    def getExportAsRencatOutput(self):
        return self._exportAsRencatOutput

    def getExportAsRencatOutputPath(self):
        return self._exportAsRencatOutputPath
        
    
        
    def getSaveFacilityLevelResults(self): 
        return self._saveFacilityLevelResults
        
    def getPerCapitaPerFacilityPerServiceTableOutputPath(self): 
        now = datetime.now().strftime('%Y-%m-%d-%H%M')
        if self.getPerCapitaCsvOutputPath() is None: 
            raise ValueError("Can't save the interim benefits results without the per-capita csv file being saved, sorry. Do that first.")
        outpath = os.path.join(
            os.path.split(self.getPerCapitaCsvOutputPath())[0], 
            f"perCapitaPerFacilityPerServiceBenefits-{now}.npy"
        )
        return outpath

    def getPerCapitaPerFacilityPerServiceIndexOutputPath(self): 
        now = datetime.now().strftime('%Y-%m-%d-%H%M')
        if self.getPerCapitaCsvOutputPath() is None: 
            raise ValueError("Can't save the interim benefits results without the per-capita csv file being saved, sorry. Do that first.")
        outpath = os.path.join(
            os.path.split(self.getPerCapitaCsvOutputPath())[0], 
            f"perCapitaPerFacilityPerServiceBenefitsIndices-{now}.json"
        )
        return outpath
    
    # -----------------SETTERS------------------

    # ---- facility setters ----
    def setFacilitiesLayerName(self, layerName: str):
        self._facilitiesLayerName = layerName

    def setFacilitiesLayer(self, layer: QgsVectorLayer):
        self._facilitiesLayer = layer

    def setFacilitiesLayerData(self, data: list):
        self._facilitiesLayerData = data

    def setFacilityLatitudes(self, vals: np.array):
        self._facilityLatitudes = vals

    def setFacilityLongitudes(self, vals: np.array):
        self._facilityLongitudes = vals

    def setFacilityIndexField(self, field: str):
        self._facilitiesIndexFieldName = field

    def setHasFacilityLatLongs(self, hc: bool):
        self._facilitiesHaveLatLongs = hc

    def setFacilityLatField(self, field: str):
        self._facilitiesLatField = field

    def setFacilityLongField(self, field: str):
        self._facilitiesLongField = field

    def setFacilitySectorField(self, field: str):
        self._facilitiesSectorField = field

    # -----population ---------
    def setPopulationLayerName(self, layerName: str):
        self._populationLayerName = layerName

    def setPopulationHasCentroids(self, hc: bool):
        self._populationHasCentroids = hc

    def setPopulationLongField(self, field: str):
        self._populationCentroidLongField = field

    def setPopulationLatField(self, field: str):
        self._populationCentroidLatField = field

    def setPopulationIndexField(self, field: str):
        self._populationIndexFieldName = field

    def setPopulationPopulationField(self, field: str):
        self._populationPopulationFieldName = field

    def setPopulationAttainFactorField(self, field: str):
        self._populationAttainFactorFieldName = field

    def setPopulationCentroidsLayer(self, layer: QgsVectorLayer):
        self._populationCentroidsLayer = layer

    def setPopulationLatitudes(self, vals: np.array):
        self._populationCentroidLats = vals

    def setPopulationLongitudes(self, vals: np.array):
        self._populationCentroidLongs = vals

    def setPopulationLayerData(self, data: list):
        """
        Returns: list of lists
        """
        self._populationLayerData = data

    def setPopulationLayer(self, layer: QgsVectorLayer):
        self._populationLayer = layer

    # -----sector to service mapping
    def setSectorToServiceLayerName(self, layerName: str):
        self._sectorToServiceLayerName = layerName

    def setSectorToServiceLayer(self, layer: QgsVectorLayer):
        self._sectorToServiceLayer = layer

    def setSectorToServiceSectorField(self, field: str):
        self._sectorToServiceSectorField = field

    def setSectorToServiceEpfField(self, field: str):
        self._sectorToServiceEpfField = field

    def setSectorToServiceZdeField(self, field: str):
        self._sectorToServiceZdeField = field

    # -------facility service layer-
    def setFacilityServiceLayer(self, layer: QgsVectorLayer):
        self._facilityServiceLayer = layer

    def setFacilityServiceLayerData(self, data: list):
        self._facilityServiceLayerData = data

    # ------- exclusion profile setters ----

    def setExclusionLayerName(self, layerName: str):
        self._exclusionLayerName = layerName

    def setExclusionLayer(self, layer: QgsVectorLayer):
        self._exclusionLayer = layer

    def setHasExclusionLayer(self, hc: bool):
        self._hasExclusionLayer = hc

    def setSLReduction(self, amt):
        """
        This is a scalar percent value (0-100), not an array.
        """
        self._SLReduction = amt

    def setSLReductionArray(self, arr: np.array):
        self._SLReductionArray = arr

    # ---------export setters ----------
    def setExportToCsv(self, hc: bool):
        self._exportToCsv = hc

    def setPerCapitaCsvOutputPath(self, path: str):
        self._perCapitaCsvOutputPath = path

    def setAggregatedCsvOutputPath(self, path: str):
        self._aggregatedCsvOutputPath = path

    def setExportToRencat(self, hc: bool):
        self._exportToRencat = hc

    def setRencatInputPath(self, path: str):
        self._exportToRencatPath = path

    def setExportAsRencatOutput(self, hc: bool):
        self._exportAsRencatOutput = hc

    def setExportAsRencatOutputPath(self, path: str):
        self._exportAsRencatOutputPath = path
