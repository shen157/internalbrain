import math


def percentile(
    values,
    percentile_value
):
    """
    Calculate percentile using linear interpolation.

    Example:
    percentile(values, 50) -> p50
    percentile(values, 95) -> p95
    """

    if not values:
        return None


    sorted_values = sorted(
        values
    )


    if len(sorted_values) == 1:
        return sorted_values[0]


    position = (
        percentile_value
        / 100
        * (
            len(sorted_values)
            - 1
        )
    )


    lower_index = math.floor(
        position
    )

    upper_index = math.ceil(
        position
    )


    if (
        lower_index
        ==
        upper_index
    ):

        return sorted_values[
            lower_index
        ]


    lower_value = (
        sorted_values[
            lower_index
        ]
    )

    upper_value = (
        sorted_values[
            upper_index
        ]
    )


    weight = (
        position
        -
        lower_index
    )


    return (
        lower_value
        +
        (
            upper_value
            -
            lower_value
        )
        *
        weight
    )


def latency_summary(
    latencies_ms
):

    if not latencies_ms:

        return {
            "count": 0,
            "mean_ms": None,
            "min_ms": None,
            "max_ms": None,
            "p50_ms": None,
            "p95_ms": None
        }


    return {

        "count":
            len(
                latencies_ms
            ),

        "mean_ms":
            sum(
                latencies_ms
            )
            /
            len(
                latencies_ms
            ),

        "min_ms":
            min(
                latencies_ms
            ),

        "max_ms":
            max(
                latencies_ms
            ),

        "p50_ms":
            percentile(
                latencies_ms,
                50
            ),

        "p95_ms":
            percentile(
                latencies_ms,
                95
            )
    }