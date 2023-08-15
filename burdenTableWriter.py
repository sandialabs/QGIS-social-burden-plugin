import tempfile
import pandas as pd
from . import QgsSBCalcDataBridge
from . import SBCalculator


class burdenTableWriter:
    """
    Uses the results of the calculations and produces pandas dataframes
    or csv tables of the results in a standard format.
    """

    def __init__(
        self,
        dataBridge: QgsSBCalcDataBridge.QgsSBCalcDataBridge,
        SBC: SBCalculator.SBCalculator,
    ):
        self._dataBridge = dataBridge
        self._SBCalculator = SBC

    def generatePerAreaTable(self):
        """
        Helper function for munging the layers - given the appropriate
        arrays, creates a table (as pandas dataframe) that contains that information
        in the way that we want.

        Relies on having previous calculations and other fields available
        in the SBCalculator AND dataBridge objects.
        """

        ret = pd.DataFrame(
            self._SBCalculator.getBurdenArray(),
            columns=self._dataBridge.getServiceNames(),
        )
        ret.insert(ret.shape[1], "total", self._SBCalculator.getPerCapitaTotalBurden())
        ret.insert(
            ret.shape[1],
            "W_total",
            self._SBCalculator.getPerCapitaWeightedTotalBurden(),
        )

        if (
            self._dataBridge.getPopulationHasCentroids()
        ):  # if the centroids have been specified
            ret.insert(
                0,
                self._dataBridge.getPopulationLatField(),
                self._dataBridge.getPopulationLatitudes(),
            )
            ret.insert(
                1,
                self._dataBridge.getPopulationLongField(),
                self._dataBridge.getPopulationLongitudes(),
            )
        else:  # put in the ones that were actually used
            ret.insert(
                0, "centroid_latitudes", self._dataBridge.getPopulationLatitudes()
            )
            ret.insert(
                1, "centroid_longitudes", self._dataBridge.getPopulationLongitudes()
            )

        # insert the indices
        ret.insert(
            0,
            self._dataBridge.getPopulationIndexField(),
            self._dataBridge.getPopulationDataByFieldName(
                self._dataBridge.getPopulationIndexField(), expected_type=str
            ),
        )

        return ret

    def generateTotalsTable(self):
        """
        Helper function for munging the layers - creates the table (as pandas dataframe) with the
        total-area information.

         The desired items in this table are:
        - two rows, one for population-weighted aggregates and
            one that aggregates per-capita values
        - the columns are:
            - labels for the rows
            - each of the services
            - population (NULL and total population are the values)
            - total (total per-capita burden and population-weighted total burden, respectively)

        """

        idxes = ["total per-capita", "total population-weighted"]
        ret = pd.DataFrame(
            (
                self._SBCalculator.getPerCapitaAggregatedBurdenArray(),
                self._SBCalculator.getAggregatedWeightedBurden(),
            ),
            columns=self._dataBridge.getServiceNames(),
        )
        ret.insert(0, "Agg_type", idxes)
        ret.insert(
            1, "population", [pd.NA, self._dataBridge.getPopulationTotalPopulation()]
        )
        ret.insert(
            ret.shape[1],
            "total",
            (
                self._SBCalculator.getPerCapitaAggregatedTotalBurden(),
                self._SBCalculator.getAggregatedWeightedTotalBurden(),
            ),
        )
        return ret

    def exportTableAsTempFile(self, table: pd.DataFrame):
        """
        Exports as CSV to temporary file.
        """
        tf = tempfile.NamedTemporaryFile(mode="w+", encoding="utf8", delete=False)
        tf.close()
        table.to_csv(tf.name, index=False)
        return tf

    def exportTable(self, table: pd.DataFrame, path: str):
        """
        Exports as CSV to specified path.
        """
        table.to_csv(path, index=False)
