class BaseTracker:
    def __init__(self, *args, **kwargs):
        pass

    def get_status(self, tracking_number, carrier):
        raise NotImplementedError()

    def supported_carriers(self):
        """Defines the carriers supported by this tracker.

        Returns:
            list: List of supported carriers as tuples of (carrier_code, priority),
                where priority is an integer. The carrier with the highest priority
                will be used when tracking a shipment. "*" can be used as a wildcard
                to match all carriers.

        Raises:
            NotImplementedError: When this method is not implemented by the subclass.
        """
        raise NotImplementedError()
