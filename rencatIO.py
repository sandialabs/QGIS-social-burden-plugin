import json
import pandas as pd
import numpy as np

from . import QgsSBCalcDataBridge


class rencatPopulation:
    """
    Helper class for the rencatInput
    """

    def __init__(self, popid, attainmentFactor, weight, latitude, longitude):
        self._id = (popid,)
        self._attainmentFactor = (attainmentFactor,)
        self._weight = (weight,)
        self._latitude = (latitude,)
        self._longitude = longitude

    def asDict(self):
        dct = {
            "id": self._id[0],
            "attainmentFactor": self._attainmentFactor[
                0
            ].item(),  # #since our calculations are in numpy, we need to convert
            "weight": self._weight[0].item(),
            "latitude": self._latitude[0],
            "longitude": self._longitude,
        }

        return dct

    def id(self):
        return self._id[0]


class rencatFacility:
    """
    Helper class for the rencatInput
    """

    def __init__(
        self, objectid, latitude, longitude, sector, zeroDistanceEffort, effortPerFoot
    ):
        self._id = (objectid,)
        self._latitude = (latitude,)
        self._longitude = (longitude,)
        self._sector = (sector,)
        self._zeroDistanceEffort = (zeroDistanceEffort,)
        self._effortPerFoot = effortPerFoot

    def asDict(self):
        dct = {
            "id": str(self._id[0]),
            "latitude": self._latitude[0],
            "longitude": self._longitude[0],
            "category": self._sector[0],
            "zeroDistanceEffort": self._zeroDistanceEffort[0],
            "effortPerFoot": self._effortPerFoot,
        }

        return dct

    def id(self):
        return self._id


class rencatSectorToService:
    """
    Helper class for the rencatInput
    """

    def __init__(self, sectors, services, sectorToServiceArray):
        self._sectors = (sectors,)
        self._services = (services,)
        self._sectorToServiceArray = sectorToServiceArray

    def asDict(self):
        ret = {}

        for idx, sector in enumerate(self._sectors[0]):
            tmp = self._sectorToServiceArray[idx, :].tolist()

            ret[sector] = {
                service: float(tmp[servidx])
                for servidx, service in enumerate(self._services[0])
                if tmp[servidx] > 0
            }
        return ret


class rencatInput:
    """
    Helper class for the rencatInputWriter
    """

    def __init__(self):
        self._facilities = {}
        self._benefits = {}
        self._populationBlocks = {}
        self._facilityStatus = {}
        self._model = {}

    def asDict(self):
        self._model = {
            "facilities": [self._facilities[fac].asDict() for fac in self._facilities],
            "benefits": self._benefits.asDict(),
            "populationBlocks": [
                self._populationBlocks[pop].asDict() for pop in self._populationBlocks
            ],
            "serviceWeights": {},
        }

        return {"model": self._model, "facilityStatus": self._facilityStatus}

    def addPopulation(self, rpop: rencatPopulation):
        """
        Will raise error if asked to overwrite existing population id. this is why
        indices must be unique.
        """

        if rpop.id() in self._populationBlocks:
            raise ValueError(
                "Found repeated population index when writing out for ReNCAT."
            )
        else:
            self._populationBlocks[rpop.id()] = rpop

    def addFacility(self, fac: rencatFacility):
        if fac.id() in self._facilities:
            raise ValueError(
                "Found repeated facility index when writing out for ReNCAT."
            )
        else:
            self._facilities[fac.id()] = fac
            self._facilityStatus[fac.id()[0]] = 1

    def addSectorToServiceTable(self, sst: rencatSectorToService):
        self._benefits = sst

    def updateFacilityStatus(self, facilityId, statusLevel):
        self._facilityStatus[facilityId] = statusLevel

    def numFacilities(self):
        return len(self._facilities)

    def numPopulationBlocks(self):
        return len(self._populationBlocks)


class rencatInputWriter:
    def __init__(self, databridge: QgsSBCalcDataBridge.QgsSBCalcDataBridge):
        self._dataBridge = databridge

    def _createRencatInputFile(
        self,
        outputPath,
        populationIds,
        attainmentFactors,
        weights,
        popLats,
        popLongs,
        facilityIds,
        facilityLats,
        facilityLongs,
        facilitySectors,
        facilityZeroDistanceEfforts,
        facilityEffortsPerFoot,
        serviceList,
        sectorList,
        sectorToServiceTable,
        hasExclusionLayer=False,
        facilityStatus=None,
    ):
        """
        Creates the rencat input file that is an optional output of this
        plugin.

        inputs:
            outputPath: str
                the path to which to write the output file.

            populationIds: list or other 1-d iterable.
                Indexes of all the different population groups.

            attainmentFactors: list or other 1-d iterable.
                Values of the population groups' attainment factors.

            weights: list or other 1-d iterable.
                Populations of the population groups.

            popLats: list or other 1-d iterable.
                Latitudes of the population groups' centroids.

            popLongs: list or other 1-d iterable.
                Longitudes of the population groups' centroids.

            facilityIds: list or other 1-d iterable.
                Indexes of the different facilities.

            facilityLats: list or other 1-d iterable.
                Latitudes of the facilities.

            facilityLongs: list or other 1-d iterable.
                Longitudes of the facilities.

            facilitySectors: list or other 1-d iterable.
                Sector of each facility.

            facilityZeroDistanceEfforts: list or other 1-d iterable.
                Zero-distance effort of each facility.

            facilityEffortsPerFoot: list or other 1-d iterable.
                Effort per foot of each facility.

            serviceList: list or other 1-d iterable.
                List of service types.

            sectorList: list or other 1-d iterable.
                List of available sectors
                whose facilities may provide services.

            sectorToServiceTable: 2-d numpy array of shape (number of sectors,
                number of services).

                Should be in the same order as the sectorList and
                the serviceList, respectively. Values are the service levels
                provided by the given sector of the given service.


            hasExclusionLayer: bool (optional, default False)
                Whether an exclusion layer
                is being taken into account.


            facilityStatus: optional, default None, but required if hasExclusionLayer
                is True (ignored if False).

                If being used, is a list or
                other 1-d iterable, of length (number of facilities), containing the
                amount of service remaining at the facility in question (range 0-1. If
                hasExclusionLayer is false, all facilities will be assumed to
                be providing their full level of service.


        output: none

        side effects: writes a json string to the provided output path,
            containing the information that would be used to run the command line
            standalone burden calculator part of rencat, in the format
            rencat likes.
        """

        # create the rencat input class object
        r_I = rencatInput()

        # add a bunch of facilities to it
        for idx, val in enumerate(facilityIds):
            r_I.addFacility(
                rencatFacility(
                    val,
                    facilityLats[idx],
                    facilityLongs[idx],
                    facilitySectors[idx],
                    facilityZeroDistanceEfforts[idx],
                    facilityEffortsPerFoot[idx],
                )
            )

        # add the population groups
        for idx, val in enumerate(populationIds):
            r_I.addPopulation(
                rencatPopulation(
                    val,
                    attainmentFactors[idx],
                    weights[idx],
                    popLats[idx],
                    popLongs[idx],
                )
            )

        # add the sector to service mapping
        r_I.addSectorToServiceTable(
            rencatSectorToService(sectorList, serviceList, sectorToServiceTable)
        )

        # if there was an exclusion profile,
        # update the service levels of the facilities
        if hasExclusionLayer == True:
            for idx, val in enumerate(facilityIds):
                r_I.updateFacilityStatus(val, facilityStatus[idx])

        # get the thing as a dict.
        rDict = r_I.asDict()

        # write to file
        with open(outputPath, "w") as f:
            json.dump(rDict, f, indent=4, ensure_ascii=False)

    def createRencatInputFile(self):
        self._createRencatInputFile(
            self._dataBridge.getRencatInputPath(),
            self._dataBridge.getPopulationDataByFieldName(
                self._dataBridge.getPopulationIndexField(), expected_type=str
            ),
            self._dataBridge.getPopulationDataByFieldName(
                self._dataBridge.getPopulationAttainFactorField(), expected_type=float
            ),
            self._dataBridge.getPopulationDataByFieldName(
                self._dataBridge.getPopulationPopulationField(), expected_type=int
            ),
            self._dataBridge.getPopulationLatitudes().tolist(),
            self._dataBridge.getPopulationLongitudes().tolist(),
            self._dataBridge.getFacilityDataByFieldName(
                self._dataBridge.getFacilityIndexField(), expected_type=str
            ),
            self._dataBridge.getFacilityLatitudes().tolist(),
            self._dataBridge.getFacilityLongitudes().tolist(),
            self._dataBridge.getFacilityDataByFieldName(
                self._dataBridge.getFacilitySectorField(), expected_type=str
            ),
            self._dataBridge.getFacilityServiceDataByFieldName(
                self._dataBridge.getSectorToServiceZdeField(), expected_type=float
            ),
            self._dataBridge.getFacilityServiceDataByFieldName(
                self._dataBridge.getSectorToServiceEpfField(), expected_type=float
            ),
            self._dataBridge.getServiceNames(),  # list of the names of the services
            self._dataBridge.getSectors(),  # list of available sectors, in order
            self._dataBridge.getSectorToServiceArray(),
            hasExclusionLayer=self._dataBridge.getHasExclusionLayer(),
            facilityStatus=(1 - (self._dataBridge.getSLReductionArray() * 1e-2)),
        )


class rencatOutputWriter:
    def _createPopulationBlockDct(self, perAreaOutputTable: pd.DataFrame):
        """
        Creates a dictionary describing the population blocks, structured as:
        {population block identifier : dkt}
        where dkt is itself a dictionary, structured as
            "overallBurden" : <value>
            "serviceBurden" : dkt2

        and dkt2 is again a dictionary, structured as
            service: burden associated with that service (float)
        """

        dct = {}
        to_drop = [perAreaOutputTable.columns[i] for i in [0, 1, -1, -2]]
        droptable = perAreaOutputTable.drop(columns=to_drop)
        for popgroup in perAreaOutputTable.index:
            popdct = {}
            popdct["overallBurden"] = perAreaOutputTable.loc[popgroup, "total"]
            popdct["serviceBurden"] = droptable.loc[popgroup].to_dict()
            dct[popgroup] = popdct

        return dct

    def _createOverallBurdens(self, aggregatedOutputTable: pd.DataFrame):
        """
        Creates a tuple describing the overall burden, structured as:
        (float, dict)
        where the float is the overall population-weighted burden,
        and the dict's keys are the services and the
        values are the weighted aggregated burden values

        """

        overallBurden = aggregatedOutputTable.loc["total population-weighted", "total"]

        overallBurdenDct = (
            aggregatedOutputTable.drop(columns=["population", "total"])
            .loc["total population-weighted"]
            .to_dict()
        )

        return (overallBurden, overallBurdenDct)

    def _createRencatOutputDict(
        self, perAreaOutputTable: pd.DataFrame, aggregatedOutputTable: pd.DataFrame
    ):
        """
        creates the rencat output-formatted file that is an optional output of this
        plugin.
        inputs:
            perAreaOutputTable
            aggregatedOutputTable

        output: a python dictionary structured in the way a rencat output file is structured.

        side effects: none
        """

        dct = {}
        dct["populationBlockBurden"] = self._createPopulationBlockDct(
            perAreaOutputTable
        )

        dct["overallBurden"], dct["overallServiceBurden"] = self._createOverallBurdens(
            aggregatedOutputTable
        )

        return dct

    def writeRencatOutput(
        self, outputPath: str, perAreaOutputTable: str, aggregatedOutputTable: str
    ):
        """
        Generates a ReNCAT-output style formatted json file and saves to outputPath.

        inputs:
            outputPath: string
                Path to which to save the json file.

            perAreaOutputTable: string
                path to a per-area burden table created by the QGIS social burden calculator.

            aggregatedOutputTable: string
                path to an aggregated burden table created by the QGIS social burden calculator.



        outputs: none

        side effects: writes json string to file.
        """
        paT = pd.read_csv(perAreaOutputTable, index_col=0, dtype={0: str})

        aT = pd.read_csv(aggregatedOutputTable, index_col=0)

        dct = self._createRencatOutputDict(paT, aT)

        with open(outputPath, "w") as f:
            json.dump(dct, f, indent=4)
