# Standard imports
import numpy as np
import json
import logging
from dateutil import parser
import math
import pandas as pd
import attrdict as ad

# Our imports
import emission.analysis.point_features as pf
import emission.storage.decorations.useful_queries as taug
import emission.storage.decorations.location_queries as lq
import emission.core.get_database as edb

np.set_printoptions(suppress=True)

def filter_accuracy(points_df):
    """
    Returns a data frame with the low accuracy points filtered.
    We return a new dataframe that has been reindexed to the new set of points rather than
    a filtered dataframe with the original index because otherwise, we are not
    able to apply any further boolean filter masks to it.
    """
    print "filtering points %s" % points_df[points_df.mAccuracy > 200].index
    accuracy_filtered_df = pd.DataFrame(points_df[points_df.mAccuracy < 200].to_dict('records'))
    print "filtered list size went from %s to %s" % (points_df.shape, accuracy_filtered_df.shape)
    return accuracy_filtered_df

def add_speed(points_df):
    """
    Returns a new dataframe with an added "speed" column.
    The speed column has the speed between each point and its previous point.
    The first row has a speed of zero.
    """
    point_list = [ad.AttrDict(row) for row in points_df.to_dict('records')]
    zipped_points_list = zip(point_list, point_list[1:])
    speeds = [pf.calSpeed(p1, p2) for (p1, p2) in zipped_points_list]
    speeds.insert(0, 0)
    with_speeds_df = pd.concat([points_df, pd.Series(speeds, name="speed")], axis=1)
    return with_speeds_df

def get_section_points(section):
    if section.source == "raw_auto":
        section.user_id = section.id
        section.loc_filter = section.filter
    df = lq.get_points_for_section(section)
    return df

def filter_points(section_df, outlier_algo, filtering_algo):
    """
    Filter the points that correspond to the section object that is passed in.
    The section object is an AttrDict with the startTs and endTs fields.
    Returns a filtered df with the index after the initial filter for accuracy
    TODO: Switch this to the section wrapper object going forward
    TODO: Note that here, we assume that the data has already been chunked into sections.
    But really, we need to filter (at least for accuracy) before segmenting in
    order to avoid issues like https://github.com/e-mission/e-mission-data-collection/issues/45
    """
    accuracy_filtered_df = filter_accuracy(section_df)
    with_speeds_df = add_speed(accuracy_filtered_df)
    # if filtering algo is none, there's nothing that can use the max speed
    if outlier_algo is not None and filtering_algo is not None:
        maxSpeed = outlier_algo.get_threshold(with_speeds_df)
        # TODO: Is this the best way to do this? Or should I pass this in as an argument to filter?
        # Or create an explicit set_speed() method?
        # Or pass the outlier_algo as the parameter to the filtering_algo?
        filtering_algo.maxSpeed = maxSpeed
    if filtering_algo is not None:
        filtering_algo.filter(with_speeds_df)
        return accuracy_filtered_df[filtering_algo.inlier_mask_]
    else:
        return accuracy_filtered_df
