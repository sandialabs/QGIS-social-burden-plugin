import numpy as np
import warnings, pdb

from . import QgsSBCalcDataBridge


class SBCalculator:
    def __init__(self, dataBridge: QgsSBCalcDataBridge.QgsSBCalcDataBridge):
        self._units = "feet"
        self._SLReduceArray = None
        self._distancesPopByFacs = None
        self._ZdeArray = None  # zero distance effort
        self._EpfArray = None  # effort per foot
        self._serviceLevelArray = None
        self._attainFactorArray = None
        self._populationArray = None

        self._populationToFacilitiesDistances = None  # this is derived, not set

        self._burdenArray = None  # this is derived, not set.

        self.importFromDataBridge(dataBridge)  # make sure all fields are filled

    def importFromDataBridge(self, dataBridge: QgsSBCalcDataBridge.QgsSBCalcDataBridge):
        self.setSLReduce(dataBridge.getSLReductionArray())
        self.setZeroDistanceEffort(
            dataBridge.getFacilityServiceDataByFieldName(
                dataBridge.getSectorToServiceZdeField(), expected_type=float
            )
        )
        self.setEffortPerDistanceArray(
            dataBridge.getFacilityServiceDataByFieldName(
                dataBridge.getSectorToServiceEpfField(), expected_type=float
            )
        )
        self.setServiceLevelArray(dataBridge.getFacilityServiceServiceArray())
        self.setAttainFactorArray(
            dataBridge.getPopulationDataByFieldName(
                dataBridge.getPopulationAttainFactorField(), expected_type=float
            )
        )
        self.setPopulationArray(
            dataBridge.getPopulationDataByFieldName(
                dataBridge.getPopulationPopulationField(), expected_type=int
            )
        )

        self.setPopulationToFacilitiesDistances(
            self.calculatePairwiseDistances(
                dataBridge.getPopulationLatitudes(),
                dataBridge.getFacilityLatitudes(),
                dataBridge.getPopulationLongitudes(),
                dataBridge.getFacilityLongitudes(),
            )
            * 3.28084  # convert meters to feet
        )

    def _calculatePerCapitaPerFacilityBurden(self):
        """Calculate per-person benefits from each facility/cbg pairing for each service type.
        that is, service level * (1- reduction/100) * attainment factor, all divided by
        zero distance effort + (distance in feet * effort per foot).
        There's some matrix dimension games going on here as well; see comments on this
        function for details.

        Saves the resulting burden array, which maps
        facilities to sectors.

        The resulting burden array is of shape (num population groups, num services)

        """
        # let:
        # the number of services be s.
        # the number of facilities be m
        # the number of population groups be n
        # Working this out in increasing dimensionality below.

        # For a given facility and population group, we want to end up with an (s,) length array.
        # service level is of shape (s,), while all other items are scalars, so this works well.
        # For a given population group, we then have m facilities, so we want to end with an (m,s) array
        # that describes the benefit of that population group, for all facilities and services
        # (we can aggregate the benefit across the facilities to get the benefit over the services)
        # in this case, SL is (m,s), reduction is (m,), attainment is a scalar,
        # zero-distance effort is (m,), and distance in feet and effort per foot are both (m,).
        # We multiply distance in feet and effort per foot elementwise, then add zero-distance effort.
        # This obtains an (m,) denominator.
        # in the numerator, we broadcast (1-reduction/100) across all m rows of service level,
        # then multiply by the scalar attainment factor.
        # Dividing an (m,s)-shaped array by an (m,) shaped array is not a problem, and yields
        # the correctly-shaped result.
        # Over all populations, things get messier. Ultimately, we want an (n,m,s) array (or
        # something in those three sizes, if not that order, but this programmer
        # prefers that ordering for cognitive simplicity). This array gets aggregated along the
        # middle dimension (the m facilities) to provide the benefit for each population over each
        # service.
        # service level is still of shape (m,s).
        # (1- reduction/100) is still of shpae (m,)
        # zero-distance effort and effort per foot are of shape (m,)
        # but now  attainment is of shape (n,)
        # and distance in feet is now (n,m).
        # Starting with the denominator:
        # We broadcast-multiply effort per foot and the distance in feet matrix, so that
        # each population group's effort in traveling the given distance to the m facilities is now known.
        # We broadcast-add the zero-distance efforts (which cover each facility) over all those
        # population groups. Our denominator is (n,m).
        #
        # In the numerator, we play games due to the programmer's cognitive biases.
        # As before, we broadcast-multiply (1- reduction/100) and service levels, so that
        # each facility's service level reduction is accommodated over all services.
        # Our result here is of shape (m,s). Let it be called SLR for convenience.
        # We want to broadcast-multiply SLR with
        # the attainment factors. Due to numpy broadcasting rules, to result in an
        # array of shape (n,m,s), it is easiest to first transpose SLR (to (s,m)), then
        # broadcast-multiply
        # the result by a reshaped attainment factor (now of shape (n,1)), and then transpose the
        # ultimate result. This yields an array of shape (n,m,s), which can be safely divided by our
        # denominator (n,m).
        # You may ask here, why are you multiplying by 0.01 instead of dividing by 100?
        # Because division is expensive (The issues with floating point
        # numbers for 0.01 are not particularly worrisome here.)

        # result is (n,m) due to broadcasting
        denominator = self._ZdeArray + self._EpfArray * self._distancesPopByFacs

        SLR = (
            (1 - self._SLReduceArray * 1e-2).reshape((-1, 1)) * self._serviceLevelArray
        ).transpose()

        numerator = (
            SLR.reshape((SLR.shape[0], SLR.shape[1], 1)) * self._attainFactorArray
        ).transpose()
        # numerator had darn better be (n,m,s) now.

        per_capita_per_facility_benefit_arr = numerator / (
            denominator.reshape((denominator.shape[0], denominator.shape[1], 1))
        )

        # #we now have the per-capita burden-grouped benefits,
        # broken out by service
        benefit_arr = np.sum(
            per_capita_per_facility_benefit_arr, axis=1
        )  # is of shape (num population groups, num services)

        # invert to find partial burdens.
        burden_arr = 1 / benefit_arr
        # is of shape (num cbgs, num services)

        self._burdenArray = burden_arr

    def calculateBurden(self):
        self._calculatePerCapitaPerFacilityBurden()

    def calculatePairwiseDistances(self, lat1, lat2, long1, long2):
        """
        Array-based version of latlong great circle distance calculation.
        In meters.
        ACOS(COS(RADIANS(90-Lat1)) * COS(RADIANS(90-Lat2)) + SIN(RADIANS(90-Lat1)) * SIN(RADIANS(90-Lat2)) * COS(RADIANS(Long1-Long2))) * 6.3781×10^6 m

        Inputs:
            lat1: latitudes of 1st set of points. Assume to be a (n,) numpy array
            lat2: latitudes of 2nd set of points. Assume to be a (m,) numpy array
            long1: longitudes of 1st set of points. Assume to be an (n,) numpy array
            long2: longitudes of 2nd set of points. Assume to be an (m,) numpy array

        Returns:
            (n,m) array of pairwise distances, in meters
        """
        radlatdiff = np.deg2rad(
            lat1.reshape(lat1.shape[0], 1) - lat2.reshape(lat2.shape[0], 1).T
        )  # of shape (n,m)
        radlatsum = np.deg2rad(
            lat1.reshape(lat1.shape[0], 1) + lat2.reshape(lat2.shape[0], 1).T
        )  # of shape(n,m)
        radlongdiff = np.deg2rad(
            long1.reshape(long1.shape[0], 1) - long2.reshape(long2.shape[0], 1).T
        )  # of shape (n,m)
        sinsquaredlatdiff = np.power(np.sin(radlatdiff * 0.5), 2)  # (n,m)
        sinsquaredlatsum = np.power(np.sin(radlatsum * 0.5), 2)  # (n,m)
        sinsquaredlongdiff = np.power(np.sin(radlongdiff * 0.5), 2)  # (n,m)
        res = (
            2
            * np.arcsin(
                np.sqrt(
                    sinsquaredlatdiff
                    + (1 - sinsquaredlatdiff - sinsquaredlatsum) * sinsquaredlongdiff
                )
            )
            * 6.3781e6
        )  # had better be (n,m)
        return res

    # ------- getters ------------------

    def getBurdenArray(self):
        """
        burdenArray is of shape (number of population groups, number of services)
        if it has been calculated. Else it is None.
        """
        burdenArray = self._burdenArray
        if burdenArray is None:
            raise ValueError(
                "Burden has not yet been calculated and therefore cannot be gotten."
            )
        return burdenArray

    def getPerCapitaAggregatedBurdenArray(self):
        """
        Relies on burden already having been calculated.
        Returns array of shape (number of services, )
        """
        burdenArray = self.getBurdenArray()
        if burdenArray is None:
            raise ValueError(
                "Because burden has not yet been calculated, derived calculations cannot be performed."
            )

        return np.sum(burdenArray, axis=0)

    def getPerCapitaAggregatedTotalBurden(self):
        """
        Returns the total unweighted burden over all
        services and populations - a scalar (or, perhaps more accurately,
        a length-1 numpy array)
        """
        return np.sum(self.getPerCapitaAggregatedBurdenArray())

    def getPerCapitaTotalBurden(self):
        """
        Returns burden aggregated across all services, but
        not aggregated across population groups.
        Returned array is of shape (number of population groups, )
        """
        burdenArray = self.getBurdenArray()
        if burdenArray is None:
            raise ValueError(
                "Because burden has not yet been calculated, derived calculations cannot be performed."
            )

        return np.sum(burdenArray, axis=1)

    def getPerCapitaWeightedTotalBurden(self):
        """
        Population-weighted per-population group total burden
        (aggregated across services).
        Shape (num population groups, )
        """
        return self._populationArray * self.getPerCapitaTotalBurden()

    def getAggregatedWeightedTotalBurden(self):
        """
        Population-weighted burden, aggregated over services and
        population groups.
        Shape (1,)
        """
        return np.sum(self.getPerCapitaWeightedTotalBurden())

    def getAggregatedWeightedBurden(self):
        """
        This is population-weighted burden summed over
        the population groups, but still grouped by services.
        Of shape (number of services, )
        """
        return np.sum(
            self._populationArray.reshape((-1, 1)) * self.getBurdenArray(), axis=0
        )

    # --------setters --------

    def setSLReduce(self, SLR: np.array):
        self._SLReduceArray = SLR

    def setPopulationToFacilitiesDistances(self, data: np.array):
        self._distancesPopByFacs = data

    def setZeroDistanceEffort(self, data: np.array):
        self._ZdeArray = data

    def setEffortPerDistanceArray(self, data: np.array):
        self._EpfArray = data

    def setServiceLevelArray(self, data: np.array):
        self._serviceLevelArray = data

    def setAttainFactorArray(self, data: np.array):
        self._attainFactorArray = data

    def setPopulationArray(self, data: np.array):
        self._populationArray = data
