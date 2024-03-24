import os

import numpy as np
import pandas as pd
import geopandas as gpd

import shapely as sh


def points(df, crs, coords, multi_indices=None):
    """
    Create a (multi)point geodataframe from df based on indices

    Parameters
    ----------
    df : a dataframe
    crs : string of CRS
    coords : a numpy array with 2 or 3 columns (z dimension)
    multi-indices : optional index to group points in multi-points
    """

    geoms = sh.points(coords)
    res, geoms = collect_by_indices(df.copy(), geoms, multi_indices)
    return res.set_geometry(gpd.array.GeometryArray(geoms), crs)


def linestrings(df, crs, coords, indices, multi_indices=None):
    """
    Create a (multi)linestring geodataframe from df based on indices

    Parameters
    ----------
    df : a dataframe
    crs : string of CRS
    coords : a numpy array with 2 or 3 columns (z dimension)
    indices : a column name in df with indices
    multi-indices : optional index to group points in multi-linestrings
    """

    geoms = sh.linestrings(coords, indices=_simple_ix(df[indices]))
    res = df.drop_duplicates(subset=indices)
    res, geoms = collect_by_indices(res, geoms, multi_indices)
    return res.set_geometry(gpd.array.GeometryArray(geoms), crs)


def polygons(df, crs, coords, ring_indices, polygon_indices, multi_indices=None):
    """
    Create a (multi)polygon geodataframe from df based on indices

    Parameters
    ----------
    df : a dataframe
    crs : string of CRS
    coords : a numpy array with 2 or 3 columns (z dimension)
    ring_indices, polygon_indices : a column name in df with unique value for rings inf polygons
    multi-indices : optional index to group points in multi-poolygons
    """

    geoms = sh.linearrings(coords, indices=_simple_ix(df[ring_indices]))
    res = df.drop_duplicates(subset=ring_indices, ignore_index=True)

    geoms = sh.polygons(geoms, indices=_simple_ix(res[polygon_indices]))
    res = res.drop_duplicates(subset=polygon_indices, ignore_index=True)

    res, geoms = collect_by_indices(res, geoms, multi_indices)

    return res.set_geometry(gpd.array.GeometryArray(geoms), crs)


def collect_by_indices(df, geoms, indices):
    """Collect single part geometries into their Multi* counterpart by indices"""

    if indices is None:
        return df, geoms

    res = df.sort_values(indices).reset_index(drop=True)

    dup = res[indices].value_counts()

    if len(dup.loc[dup > 1]) == 0:
        return df, geoms

    single_res = res.loc[res[indices].isin(dup.loc[dup == 1].index)].copy()
    single_geoms = geoms[single_res.index.to_list()].copy()

    multi_res = res.loc[res[indices].isin(dup.loc[dup > 1].index)].copy()
    geoms = geoms[multi_res.index.to_list()].copy()

    geom_types = np.unique(sh.get_type_id(geoms))

    if len(geom_types) > 1:
        raise ValueError("geoms array must have a single geom type")

    if geom_types[0] == 0:
        geoms = sh.multipoints(geoms, indices=_simple_ix(multi_res[indices]))
    elif geom_types[0] == 1:
        geoms = sh.multilinestrings(geoms, indices=_simple_ix(multi_res[indices]))
    elif geom_types[0] == 3:
        geoms = sh.multipolygons(geoms, indices=_simple_ix(multi_res[indices]))
    else:
        raise ValueError("geom_type must be Point, Linestring or Polygon")

    multi_res = multi_res.drop_duplicates(subset=indices, ignore_index=True)

    geoms = np.concatenate([single_geoms, geoms])
    res = pd.concat([single_res, multi_res])

    return res, geoms


def _simple_ix(df):
    """Create an integer array from 0, value changes on array value change"""

    array = df.to_numpy()
    if array.shape[0] < 2:
        return np.array([0])
    int_ix = array[1:] != array[:-1]
    int_ix = np.concatenate([np.array([False]), int_ix], axis=0)
    return np.cumsum(int_ix)
