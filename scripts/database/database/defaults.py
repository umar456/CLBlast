
# This file is part of the CLBlast project. The project is licensed under Apache Version 2.0. This file follows the
# PEP8 Python style guide and uses a max-width of 120 characters per line.
#
# Author(s):
#   Cedric Nugteren <www.cedricnugteren.nl>

import pandas as pd

import clblast
import bests


def set_default_device(database_entry):
    """Sets the device name and parameters to some default values"""
    database_entry["device"] = clblast.DEVICE_NAME_DEFAULT
    database_entry["device_compute_units"] = 0
    database_entry["device_core_clock"] = 0
    return database_entry


def set_default_time(database_entry):
    """Sets the execution time to some default value"""
    database_entry["time"] = 0.0
    return database_entry


def calculate_defaults(database, calculate_common_best=True):
    """Sets defaults for devices of the same type/vendor. An option determines how to compute the defaults."""
    database_defaults = pd.DataFrame()

    # Defaults per combination of device vendors and device types (e.g. AMD GPU)
    database_type_vendor = database.groupby(clblast.DEVICE_TYPE_ATTRIBUTES + clblast.KERNEL_ATTRIBUTES + ["kernel"] +
                                            clblast.ARGUMENT_ATTRIBUTES)
    for group_name, database_group in database_type_vendor:
        if calculate_common_best:
            default_values = get_common_best(database_group, group_name)
        else:
            default_values = get_smallest_best(database_group)
        default_values = set_default_device(default_values)
        default_values = set_default_time(default_values)
        database_defaults = database_defaults.append(default_values, ignore_index=True)

    # Checks for mis-matched arguments
    groups = database_defaults.groupby(clblast.DEVICE_TYPE_ATTRIBUTES + clblast.KERNEL_ATTRIBUTES + ["kernel"])
    for group_name, database_group in groups:
        if len(database_group) != 1:
            description = database_group["kernel"].min() + " " + database_group["device_vendor"].min()
            print("[WARNING] Entries for a single kernel with multiple argument values: " + description)

    # Defaults over all device types and vendors
    groups = database.groupby(clblast.KERNEL_ATTRIBUTES + ["kernel"] + clblast.ARGUMENT_ATTRIBUTES)
    for group_name, database_group in groups:
        default_values = get_smallest_best(database_group)
        default_values["device_vendor"] = clblast.VENDOR_DEFAULT
        default_values["device_type"] = clblast.DEVICE_TYPE_DEFAULT
        default_values = set_default_device(default_values)
        default_values = set_default_time(default_values)
        database_defaults = database_defaults.append(default_values, ignore_index=True)

    # Database with both types of defaults only
    return database_defaults


def get_smallest_best(database):
    """Sets defaults based on the smallest values of all known entries. The average might be better for performance but
    some parameters might not be supported on other devices."""
    database_best_results = bests.get_best_results(database)
    return database_best_results.min(axis=0)


def get_common_best(database, group_name):
    """Sets defaults based on the best values of entries supported by all devices. This might cause a problem in case
    not every device was tuned with the same parameters."""
    # TODO: Quite a bit slower than the above `get_smallest_best` method

    # Counts the number of devices in this group
    num_devices = len(database.groupby(clblast.DEVICE_ATTRIBUTES))

    # Removes columns without any values
    database = database.dropna(axis=1, how='all')

    # Retrieves the parameter names for this kernel
    all_column_names = list(database.columns.values)
    parameter_column_names = [c for c in all_column_names if "parameters." in c]

    # Removes entries which are not available for all devices
    database_by_parameters = database.groupby(parameter_column_names)
    database_common = database_by_parameters.filter(lambda x: len(x) == num_devices)

    # Fall back to another method in case there are no shared entries at all across devices
    if len(database_common) == 0:
        # print("[database] Skipping: " + str(group_name) + " with devices: %d %d " % (num_devices, len(database)))
        return get_smallest_best(database)

    # Computes the sum of the execution times over the different devices
    database_common_by_parameters = database_common.groupby(parameter_column_names)
    group_times = database_common_by_parameters['time'].transform(sum)
    database_common.loc[:, 'group_time'] = group_times

    # Retrieves the entries with the best execution time
    best_time = database_common["group_time"].min()
    database_bests = database_common[database_common["group_time"] == best_time]

    # Retrieves one example only (the parameters are the same anyway)
    database_bests = database_bests.drop_duplicates(["group_time"])
    # print("[database] " + str(group_name) + " with devices: " + str(num_devices) + " " + str(database_bests.shape))
    assert len(database_bests) == 1

    return database_bests
