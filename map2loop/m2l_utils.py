import sys
import geopandas as gpd
import pandas as pd
from map2loop.m2l_enums import VerboseLevel
from map2loop.m2l_enums import Datatype
from shapely.geometry.polygon import Polygon
from shapely.geometry.multipolygon import MultiPolygon
import numpy as np
import rasterio
import rasterio.warp
import rasterio.mask
import fiona
import re
import os
from urllib.request import urlopen
from math import (
    sin,
    cos,
    atan2,
    asin,
    radians,
    degrees,
    sqrt,
    pow,
    acos,
    fmod,
    fabs,
    floor,
)
from owslib.wcs import WebCoverageService
import netCDF4
import time
import functools
import beartype

############################################
# get value from a rasterio raster at location x,y (real world coords)
#
# value_from_raster(dataset,locations)
# Args:
# dataset rasterio format georeferenced dataset
# locations list of x,y locations in same coordinate system for which values will be calculated Returns:
# list of values for specified lcoations
#
# Given rasterio georeferenced grid of data, return value at list of locations stored in x1,y1 using same projection. From...
############################################


def value_from_raster(dataset, locations):
    # print(locations[0][0],locations[0][1],dataset.bounds[0],dataset.bounds[1],dataset.bounds[2],dataset.bounds[3])
    if (
        locations[0][0] > dataset.bounds[0]
        and locations[0][0] < dataset.bounds[2]
        and locations[0][1] > dataset.bounds[1]
        and locations[0][1] < dataset.bounds[3]
    ):
        for val in dataset.sample(locations):
            value = str(val).replace("[", "").replace("]", "")
        return value
    else:
        return -999


def bilinear_interpolation(x, y, z01, z11, z00, z10):
    def linear_interpolation(x, z0, z1):
        return z0 * (1 - x) + z1 * x

    return linear_interpolation(
        y, linear_interpolation(x, z00, z10), linear_interpolation(x, z01, z11)
    )


#################################
#  Maybe use https://portal.opentopography.org/otr/getdem?demtype=SRTMGL3&west=-120.168457&south=36.738884&east=-118.465576&north=38.091337&outputFormat=GTiff as univeral solution?
# or SRTMGL1 for higher res probs not needed
#################################

############################################
# get value from two rasterio rasters (dtm and depth to basement) at location x,y (real world coords)
#
# value_from_raster(dtm,dtb,dtb_null,locations)
# Args:
# dtm rasterio format georeferenced dtm grid
# dtb rasterio format georeferenced dtb grid
# dtb_null value when zero cover thickness
# cover_map boolean wrt to use of dtb
# locations list of x,y locations in same coordinate system for which values will be calculated Returns:
# list of values for specified lcoations
#
# Given rasterio georeferenced grid of dtm and maybe dtb, return value at list of locations stored in x1,y1 using same projection. From...
############################################


def value_from_dtm_dtb(dtm, dtb, dtb_null, cover_map, locations):
    dtm_arr = dtm.read(1)
    bounds = dtm.bounds
    minlong = bounds.left
    minlat = bounds.bottom
    maxlong = bounds.right
    maxlat = bounds.top
    xscale = (maxlong - minlong) / dtm_arr.shape[1]
    yscale = (maxlat - minlat) / dtm_arr.shape[0]
    corners = np.zeros((4, 4))
    zvals = np.zeros((4))
    corners[0][0] = (
        minlong
        + (floor((locations[0][0] - minlong - (xscale / 2)) / xscale) * xscale)
        + (xscale / 2)
    )
    corners[0][1] = (
        minlat
        + (floor((locations[0][1] - minlat - (yscale / 2)) / yscale) * yscale)
        + (yscale / 2)
    )
    corners[1][0] = corners[0][0] + xscale
    corners[1][1] = corners[0][1]
    corners[2][0] = corners[0][0]
    corners[2][1] = corners[0][1] + yscale
    corners[3][0] = corners[0][0] + xscale
    corners[3][1] = corners[0][1] + yscale
    delx = (locations[0][0] - corners[0][0]) / xscale
    dely = (locations[0][1] - corners[0][1]) / yscale

    for i in range(4):
        corner = [(corners[i][0], corners[i][1])]
        # print(corner[0][0],dtm.bounds[0],dtm.bounds[2],corner[0][1],dtm.bounds[1],dtm.bounds[3])
        if (
            corner[0][0] > dtm.bounds[0]
            and corner[0][0] < dtm.bounds[2]
            and corner[0][1] > dtm.bounds[1]
            and corner[0][1] < dtm.bounds[3]
        ):
            for val in dtm.sample(corner):
                zvals[i] = float(str(val).replace("[", "").replace("]", ""))
        else:
            return -999
    value_dtm = bilinear_interpolation(
        delx, dely, zvals[2], zvals[3], zvals[0], zvals[1]
    )

    if cover_map:
        if (
            locations[0][0] > dtm.bounds[0]
            and locations[0][0] < dtm.bounds[2]
            and locations[0][1] > dtm.bounds[1]
            and locations[0][1] < dtm.bounds[3]
            and locations[0][0] > dtb.bounds[0]
            and locations[0][0] < dtb.bounds[2]
            and locations[0][1] > dtb.bounds[1]
            and locations[0][1] < dtb.bounds[3]
        ):
            dtb_arr = dtb.read(1)
            bounds = dtb.bounds
            minlong = bounds.left
            minlat = bounds.bottom
            maxlong = bounds.right
            maxlat = bounds.top
            xscale = (maxlong - minlong) / dtb_arr.shape[1]
            yscale = (maxlat - minlat) / dtb_arr.shape[0]
            corners = np.zeros((4, 4))
            zvals = np.zeros((4))
            corners[0][0] = (
                minlong
                + (floor((locations[0][0] - minlong - (xscale / 2)) / xscale) * xscale)
                + (xscale / 2)
            )
            corners[0][1] = (
                minlat
                + (floor((locations[0][1] - minlat - (yscale / 2)) / yscale) * yscale)
                + (yscale / 2)
            )
            corners[1][0] = corners[0][0] + xscale
            corners[1][1] = corners[0][1]
            corners[2][0] = corners[0][0]
            corners[2][1] = corners[0][1] + yscale
            corners[3][0] = corners[0][0] + xscale
            corners[3][1] = corners[0][1] + yscale
            delx = (locations[0][0] - corners[0][0]) / xscale
            dely = (locations[0][1] - corners[0][1]) / yscale

            for i in range(4):
                corner = [(corners[i][0], corners[i][1])]
                # print(corner[0][0],dtm.bounds[0],dtm.bounds[2],corner[0][1],dtm.bounds[1],dtm.bounds[3])
                if (
                    corner[0][0] > dtb.bounds[0]
                    and corner[0][0] < dtb.bounds[2]
                    and corner[0][1] > dtb.bounds[1]
                    and corner[0][1] < dtb.bounds[3]
                ):
                    for val in dtb.sample(corner):
                        zvals[i] = float(str(val).replace("[", "").replace("]", ""))
                else:
                    return -999
            if (
                zvals[0] < -10000
                or zvals[1] < -10000
                or zvals[2] < -10000
                or zvals[3] < -10000
            ):
                value_dtb = 0
            else:
                value_dtb = bilinear_interpolation(
                    delx, dely, zvals[2], zvals[3], zvals[0], zvals[1]
                )

            return str(value_dtm - value_dtb)
        else:
            return -999
    else:
        return str(value_dtm)


############################################
# turn a simple list into a list of paired data
#
# pairs(lst)
# Args:
# lst simple list a,b,c,d becomes list (a,b), (c,d) etc.
############################################
def pairs(lst):
    for i in range(1, len(lst)):
        yield lst[i - 1], lst[i]


############################################
# get dtm data from Hawaiian SRTM server and save as geotiff
#
# get_dtm_hawaii(dtm_file, minlong,maxlong,minlat,maxlat)
# Args:
# dtm_file path to location where geotiff of elevation will be saved (in WGS84 lat/long) minlong,maxlong,minlat,maxlat min/max coordinates of region of interest
# minlong,maxlong,minlat,maxlat bounding coordinates in at/long
#
# Extracts and saves to file digital terrain model from GA hosted data for Australia. Highest horizontal resolution is ? m. Min/max lat/long in WGS84 dtm_file is relative path filename.
############################################


def get_dtm_hawaii(
    path_out,
    minlong,
    maxlong,
    minlat,
    maxlat,
    url="https://pae-paha.pacioos.hawaii.edu/thredds/dodsC/srtm30plus_v11_land.ascii?elev",
):

    step_out = 0
    minxll = int(((minlong + 180) * 120) - step_out)
    maxxll = int(((maxlong + 180) * 120) + step_out)
    minyll = int(((minlat + 90) * 120) - step_out)
    maxyll = int(((maxlat + 90) * 120) + step_out)

    sizex = round(maxxll - minxll + 1)
    sizey = round(maxyll - minyll + 1)

    minxll = str(minxll)
    maxxll = str(maxxll)
    minyll = str(minyll)
    maxyll = str(maxyll)
    bbox = "[" + minyll + ":1:" + maxyll + "][" + minxll + ":1:" + maxxll + "]"

    link = url + bbox
    print(link)
    f = urlopen(link)
    myfile = f.read()
    myfile2 = myfile.decode("utf-8")
    data = myfile2.split("---------------------------------------------")
    # import re

    grid = (
        re.sub("\\[.*\\]", "", data[1])
        .replace(",", "")
        .replace("elev.elev", "")
        .replace("\n", " ")
        .replace("  ", " ")
    )
    # print(grid)
    grid = grid.split(" ")
    grid = grid[2 : (sizex * sizey) + 2]

    # OPeNDAP = np.ones((sizey,sizex), dtype='int16')
    # k=0
    # for j in range (0, sizey, 1):
    #    for i in range (0, sizex, 1):
    #        OPeNDAP[sizey-1-j][i]=int(float(grid[k]))
    #        k+=1

    OPeNDAP = np.asarray(grid, dtype=np.float16).reshape(sizey, sizex)
    OPeNDAP = OPeNDAP.astype("int16")
    OPeNDAP = np.flipud(OPeNDAP)

    transform = rasterio.transform.from_origin(
        minlong, maxlat, 0.008333333, 0.008333333
    )

    new_dataset = rasterio.open(
        path_out,
        "w",
        driver="GTiff",
        height=OPeNDAP.shape[0],
        width=OPeNDAP.shape[1],
        count=1,
        dtype=str(OPeNDAP.dtype),
        crs="+proj=longlat",
        transform=transform,
    )

    new_dataset.write(OPeNDAP, 1)
    new_dataset.close()
    print("dtm geotif saved as", path_out)


############################################
# get dtm data from topography.org server and save as geotiff
#
# get_dtm(dtm_file, minlong,maxlong,minlat,maxlat)
# Args:
# dtm_file path to location where geotiff of elevation will be saved (in WGS84 lat/long) minlong,maxlong,minlat,maxlat min/max coordinates of region of interest
# minlong,maxlong,minlat,maxlat bounding coordinates in at/long
#
# Extracts and saves to file digital terrain model from topography.org hosted data for world. Highest horizontal resolution is approx 30m m.
# Min/max lat/long in WGS84
# dtm_file is relative path filename.
############################################


def get_dtm_topography_org(path_out, minlong, maxlong, minlat, maxlat):

    link = (
        "https://portal.opentopography.org/otr/getdem?demtype=SRTMGL3&west="
        + str(minlong)
        + "&south="
        + str(minlat)
        + "&east="
        + str(maxlong)
        + "&north="
        + str(maxlat)
        + "&outputFormat=GTiff"
    )

    print(link)
    img = urlopen(link)

    f = open(path_out, "wb")
    f.write(img.read())
    f.close()
    print("dtm geotif saved as", path_out)


############################################
# get dtm data from local geotiff file, assumes same crs as model
#
# get_local_dtm(dtm_path,geotif_file,dst_src,bbox)
# Args:
# dtm_path path to location where geotiff of elevation will be saved (inlocal coords)
# geotiff_file source dtm in local coordinates
# dst_crs  local coordinate ref system
# bbox [minx,miny,maxx,maxy] in local coordinates
#
# Extracts and saves to file digital terrain model
############################################


def get_local_dtm(dtm_file, geotif_file, dst_crs, bbox):
    # get project extent
    outstep = 500  # to ensure all of dtm is availabel after clpping
    y_point_list = [
        bbox[1] - outstep,
        bbox[1] - outstep,
        bbox[3] + outstep,
        bbox[3] + outstep,
        bbox[3] + outstep,
    ]
    x_point_list = [
        bbox[0] - outstep,
        bbox[2] + outstep,
        bbox[2] + outstep,
        bbox[0] - outstep,
        bbox[0] - outstep,
    ]
    bbox_geom = Polygon(zip(x_point_list, y_point_list))
    # shapes = Polygon(zip(x_point_list, y_point_list)) # this should require to pass CRS along
    mbbox = gpd.GeoDataFrame(index=[0], crs=dst_crs, geometry=[bbox_geom])
    # write extent as a polygon in a temp shapefile
    dtm_path = os.path.split(dtm_file)[0]
    mbbox.to_file(os.path.join(dtm_path, "roi_poly_dst.shp"))
    # read temp shapefile with project extent
    with fiona.open(os.path.join(dtm_path, "roi_poly_dst.shp"), "r") as shapefile:
        shapes = [feature["geometry"] for feature in shapefile]
    # crop raster to extent
    with rasterio.open(geotif_file) as src:
        out_image, out_transform = rasterio.mask.mask(src, shapes, crop=True)
        out_meta = src.meta
    # update geotiff metadata
    out_meta.update(
        {
            "driver": "GTiff",
            "height": out_image.shape[1],
            "width": out_image.shape[2],
            "transform": out_transform,
        }
    )
    # write cropped geotiff
    with rasterio.open(dtm_file, "w", **out_meta) as dest:
        dest.write(out_image)


############################################
# get dtm data from GA SRTM server and save as geotiff
#
# get_dtm(dtm_file, minlong,maxlong,minlat,maxlat)
# Args:
# dtm_file path to location where geotiff of elevation will be saved (in WGS84 lat/long) minlong,maxlong,minlat,maxlat min/max coordinates of region of interest
# minlong,maxlong,minlat,maxlat bounding coordinates in at/long
#
# Extracts and saves to file digital terrain model from GA hosted data for Australia. Highest horizontal resolution is ? m. Min/max lat/long in WGS84 dtm_file is relative path filename.
############################################


def get_dtm(path_out, minlong, maxlong, minlat, maxlat, url="AU"):
    if url == "AU":
        url = "http://services.ga.gov.au/gis/services/DEM_SRTM_1Second_over_Bathymetry_Topography/MapServer/WCSServer?"

    bbox = (minlong, minlat, maxlong, maxlat)
    wcs = WebCoverageService(url, version="1.0.0")

    cvg = wcs.getCoverage(
        identifier="1", bbox=bbox, format="GeoTIFF", crs=4326, width=200, height=200
    )

    f = open(path_out, "wb")
    f.write(cvg.read())
    f.close()
    print("dtm geotif saved as", path_out)


############################################
# reproject a dtm
#
# reproject_dtm(dtm_file,dtm_reproj_file,src_crs,dst_crs)
# Args:
# dtm_file path to location of geotiff of elevation (in WGS84 lat/long)
# dtm_reproj_file path to location of geotiff of elevation (in projection defined by dst_crs)
# src_crs Coordinate Reference System of source geotif (normally WGS 84 lat/long (EPSG:4326))
# dst_crs Coordinate Reference System of destination geotif (any length-based projection)
#
# Returns rasterio format reprojected of filename dtm_reproj_file of grid of geotif file defined by dtm_file assuming source coordinate reference system (CRS) of src_crs and destination CRS of dsr_crs
############################################


def reproject_dtm(path_in, path_out, src_crs, dst_crs):
    with rasterio.open(path_in) as src:
        transform, width, height = rasterio.warp.calculate_default_transform(
            src.crs, dst_crs, src.width, src.height, *src.bounds
        )
        kwargs = src.meta.copy()
        kwargs.update(
            {"crs": dst_crs, "transform": transform, "width": width, "height": height}
        )

        with rasterio.open(path_out, "w", **kwargs) as dst:
            for i in range(1, src.count + 1):
                rasterio.warp.reproject(
                    source=rasterio.band(src, i),
                    destination=rasterio.band(dst, i),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs=dst_crs,
                    resampling=rasterio.warp.Resampling.nearest,
                )
            dst.close()
    print("reprojected dtm geotif saved as", path_out)


def load_and_reproject_dtm(
    polygon, dst_crs, dtm_crs="EPSG:4326", url="AU", verbose=False
):
    local_file = False
    if url == "AU":
        url = "http://services.ga.gov.au/gis/services/DEM_SRTM_1Second_over_Bathymetry_Topography/MapServer/WCSServer?"

    tb_ll = tuple(polygon.to_crs(dtm_crs).geometry.total_bounds)

    if url.startswith("http") and "wcs" in url.lower():
        # Load wcs style file and open dataset
        if verbose:
            print("Attempting to load wcs dtm data from", url)
        tb_en = polygon.geometry.total_bounds
        spacing = 30
        width = min(int((tb_en[2] - tb_en[0]) / spacing), 2048)
        height = min(int((tb_en[3] - tb_en[1]) / spacing), 2048)
        wcs = WebCoverageService(url, version="1.0.0")
        cvg = wcs.getCoverage(
            identifier="1",
            bbox=tb_ll,
            format="GeoTIFF",
            crs=4326,
            width=width,
            height=height,
        )
        memfile = rasterio.io.MemoryFile(cvg.read())
        dataset = memfile.open()
    elif url.startswith("http") and "hawaii" in url.lower():
        # Load global hawaii dataset
        bbox_str = (
            "[("
            + str(tb_ll[1])
            + "):1:("
            + str(tb_ll[3])
            + ")][("
            + str(tb_ll[0])
            + "):1:("
            + str(tb_ll[2])
            + ")]"
        )
        url = (
            "https://pae-paha.pacioos.hawaii.edu/erddap/griddap/srtm30plus_v11_land.nc?elev"
            + bbox_str
        )
        if verbose:
            print("Attempting to load netcdf dtm data from", url)
        f = urlopen(url)
        ds = netCDF4.Dataset("in-mem-file", mode="r", memory=f.read())
        spatial = (
            ds.geospatial_lon_min,
            ds.geospatial_lat_max,
            ds.geospatial_lon_resolution,
            ds.geospatial_lat_resolution,
        )
        transform = rasterio.transform.from_origin(*spatial)
        shape = ds.variables["elev"].shape
        nc_data = np.flipud(ds.variables["elev"][:][:])
        src_params = {
            "crs": ds.geospatial_bounds_crs,
            "width": shape[1],
            "height": shape[0],
            "nodata": 0,
            "transform": transform,
            "driver": "GTiff",
            "count": 1,
            "dtype": np.float32,
        }
        memfile = rasterio.io.MemoryFile()
        dataset = memfile.open(**src_params)
        dataset.write(nc_data, 1)
    elif url.startswith("http"):
        if verbose:
            print("Attempting to load digital terrin from", url)
        img = urlopen(url)
        memfile = rasterio.io.MemoryFile(img.read())
        dataset = memfile.open()
    else:
        # Load local file
        if verbose:
            print("Attempting to load dtm data from", url)
        dataset = rasterio.open(url)
        local_file = True

    # Given an open rasterio dataset reproject it into dst_crs
    new_transform, new_width, new_height = rasterio.warp.calculate_default_transform(
        dataset.crs, dst_crs, dataset.width, dataset.height, *dataset.bounds
    )
    params = dataset.meta.copy()
    params.update(
        {
            "crs": dst_crs,
            "width": new_width,
            "height": new_height,
            "nodata": 0,
            "transform": new_transform,
        }
    )
    reprojected_dtm = rasterio.io.MemoryFile()
    with reprojected_dtm.open(**params) as dst:
        data = np.zeros((new_width, new_height), dtype=np.float64)
        rasterio.warp.reproject(
            dataset.read(),
            data,
            src_transform=dataset.transform,
            src_crs=dataset.meta["crs"],
            dst_crs=dst.crs,
        )
        dst.write(data, indexes=1)
        dst.close()
    dataset.close()

    if local_file is False:
        return reprojected_dtm

    # Clip reprojected image
    reprojected_open = reprojected_dtm.open()
    out_image, out_transform = rasterio.mask.mask(
        reprojected_open, polygon.geometry, crop=True
    )
    params = reprojected_open.meta.copy()
    params.update(
        {
            "height": out_image.shape[1],
            "width": out_image.shape[2],
            "transform": out_transform,
        }
    )
    clipped_dtm = rasterio.io.MemoryFile()
    with clipped_dtm.open(**params) as dst:
        dst.write(out_image)
        dst.close()
    reprojected_open.close()

    return clipped_dtm


############################################
# get bounds of a dtm
#
# Args:
# path_in path to file rasterio can read
# dst_crs coordinate reference system of raster
# returns:
# bounding box of raster
############################################


def get_dtm_bounds(path_in, dst_crs):
    with rasterio.open(path_in) as dataset:

        # Read the dataset's valid data mask as a ndarray.
        mask = dataset.dataset_mask()
        for geom, val in rasterio.features.shapes(mask, transform=dataset.transform):

            # Transform shapes from the dataset's own coordinate
            # reference system to 28350.
            geom_rp = rasterio.warp.transform_geom(
                dataset.crs, dst_crs, geom, precision=6
            )

            # Print GeoJSON shapes to stdout.
            # print(geom_rp)
            return geom_rp


############################################
# https://gist.github.com/mhweber/cf36bb4e09df9deee5eb54dc6be74d26
# code to explode a MultiPolygon to Polygons
############################################


def explode(indf):
    #    indf = gpd.GeoDataFrame.from_file(indata)
    outdf = gpd.GeoDataFrame(columns=indf.columns)
    for idx, row in indf.iterrows():
        if type(row.geometry) == Polygon:
            outdf = outdf.append(row, ignore_index=True)
        if type(row.geometry) == MultiPolygon:
            multdf = gpd.GeoDataFrame(columns=indf.columns)
            recs = len(row.geometry)
            multdf = multdf.append([row] * recs, ignore_index=True)
            for geom in range(recs):
                multdf.loc[geom, "geometry"] = row.geometry[geom]
            outdf = outdf.append(multdf, ignore_index=True)
    return outdf


# https://github.com/earthlab/earthpy/blob/master/earthpy/clip.py
###
# earthpy.clip
# ============
# A module to clip vector data using GeoPandas.
###


def _clip_points(shp, clip_obj):
    """Clip point geometry to the clip_obj GeoDataFrame extent.
    Clip an input point GeoDataFrame to the polygon extent of the clip_obj
    parameter. Points that intersect the clip_obj geometry are extracted with
    associated attributes and returned.
    Parameters
    ----------
    shp : GeoDataFrame
        Composed of point geometry that is clipped to clip_obj.
    clip_obj : GeoDataFrame
        Reference polygon for clipping.
    Returns
    -------
    GeoDataFrame
        The returned GeoDataFrame is a subset of shp that intersects
        with clip_obj.
    """
    poly = clip_obj.geometry.unary_union
    return shp[shp.geometry.intersects(poly)]


def _clip_multi_point(shp, clip_obj):
    """Clip multi point features to the clip_obj GeoDataFrame extent.
    Clip an input multi point to the polygon extent of the clip_obj
    parameter. Points that intersect the clip_obj geometry are
    extracted with associated attributes returned.
    Parameters
    ----------
    shp : GeoDataFrame
        multipoint geometry that is clipped to clip_obj.
    clip_obj : GeoDataFrame
        Reference polygon for clipping.
    Returns
    -------
    GeoDataFrame
        The returned GeoDataFrame is a clipped subset of shp
        containing multi-point and point features.
    """

    # Explode multi-point features when clipping then recreate geom
    clipped = _clip_points(shp.explode().reset_index(level=[1]), clip_obj)
    clipped = clipped.dissolve(by=[clipped.index]).drop(columns="level_1")[
        shp.columns.tolist()
    ]

    return clipped


def _clip_line_poly(shp, clip_obj):
    """Clip line and polygon geometry to the clip_obj GeoDataFrame extent.
    Clip an input line or polygon to the polygon extent of the clip_obj
    parameter. Lines or Polygons that intersect the clip_obj geometry are
    extracted with associated attributes and returned.
    Parameters
    ----------
    shp : GeoDataFrame
        Line or polygon geometry that is clipped to clip_obj.
    clip_obj : GeoDataFrame
        Reference polygon for clipping.
    Returns
    -------
    GeoDataFrame
        The returned GeoDataFrame is a clipped subset of shp
        that intersects with clip_obj.
    """
    # Create a single polygon object for clipping
    poly = clip_obj.geometry.unary_union
    spatial_index = shp.sindex

    # Create a box for the initial intersection
    bbox = poly.bounds
    # Get a list of id's for each object that overlaps the bounding box and
    # subset the data to just those lines
    sidx = list(spatial_index.intersection(bbox))
    shp_sub = shp.iloc[sidx]

    # Clip the data - with these data
    clipped = shp_sub.copy()
    clipped["geometry"] = shp_sub.intersection(poly)

    # Return the clipped layer with no null geometry values
    return clipped[clipped.geometry.notnull()]


def _clip_multi_poly_line(shp, clip_obj):
    """Clip multi lines and polygons to the clip_obj GeoDataFrame extent.
    Clip an input multi line or polygon to the polygon extent of the clip_obj
    parameter. Lines or Polygons that intersect the clip_obj geometry are
    extracted with associated attributes and returned.
    Parameters
    ----------
    shp : GeoDataFrame
        multiLine or multipolygon geometry that is clipped to clip_obj.
    clip_obj : GeoDataFrame
        Reference polygon for clipping.
    Returns
    -------
    GeoDataFrame
        The returned GeoDataFrame is a clipped subset of shp
        that intersects with clip_obj.
    """

    # Clip multi polygons
    clipped = _clip_line_poly(shp.explode().reset_index(level=[1]), clip_obj)

    lines = clipped[
        (clipped.geometry.type == "MultiLineString")
        | (clipped.geometry.type == "LineString")
    ]
    line_diss = lines.dissolve(by=[lines.index]).drop(columns="level_1")

    polys = clipped[clipped.geometry.type == "Polygon"]
    # print(polys)
    polys.fillna("null", inplace=True)
    poly_diss = polys.dissolve(by=[polys.index]).drop(columns="level_1")

    return gpd.GeoDataFrame(pd.concat([poly_diss, line_diss], ignore_index=True))


####################################################
# master function to clip shapely geometry to a shapely polygon
####################################################


def clip_shp(shp, clip_obj):
    """Clip points, lines, or polygon geometries to the clip_obj extent.
    Both layers must be in the same Coordinate Reference System (CRS) and will
    be clipped to the full extent of the clip object.
    If there are multiple polygons in clip_obj,
    data from shp will be clipped to the total boundary of
    all polygons in clip_obj.
    Parameters
    ----------
    shp : GeoDataFrame
          Vector layer (point, line, polygon) to be clipped to clip_obj.
    clip_obj : GeoDataFrame
          Polygon vector layer used to clip shp.
          The clip_obj's geometry is dissolved into one geometric feature
          and intersected with shp.
    Returns
    -------
    GeoDataFrame
         Vector data (points, lines, polygons) from shp clipped to
         polygon boundary from clip_obj.
    Examples
    --------
    Clipping points (glacier locations in the state of Colorado) with
    a polygon (the boundary of Rocky Mountain National Park):
        >>> import geopandas as gpd
        >>> import earthpy.clip as cl
        >>> from earthpy.io import path_to_example
        >>> rmnp = gpd.read_file(path_to_example('rmnp.shp'))
        >>> glaciers = gpd.read_file(path_to_example('colorado-glaciers.geojson'))
        >>> glaciers.shape
        (134, 2)
        >>> rmnp_glaciers = cl.clip_shp(glaciers, rmnp)
        >>> rmnp_glaciers.shape
        (36, 2)
    Clipping a line (the Continental Divide Trail) with a
    polygon (the boundary of Rocky Mountain National Park):
        >>> cdt = gpd.read_file(path_to_example('continental-div-trail.geojson'))
        >>> rmnp_cdt_section = cl.clip_shp(cdt, rmnp)
        >>> cdt['geometry'].length > rmnp_cdt_section['geometry'].length
        0    True
        dtype: bool
    Clipping a polygon (Colorado counties) with another polygon
    (the boundary of Rocky Mountain National Park):
        >>> counties = gpd.read_file(path_to_example('colorado-counties.geojson'))
        >>> counties.shape
        (64, 13)
        >>> rmnp_counties = cl.clip_shp(counties, rmnp)
        >>> rmnp_counties.shape
        (4, 13)
    """
    try:
        shp.geometry
        clip_obj.geometry
    except AttributeError:
        raise AttributeError(
            "Please make sure that your input and clip GeoDataFrames have a"
            " valid geometry column"
        )

    if not any(shp.intersects(clip_obj.unary_union)):
        return ()
        # raise ValueError("Shape and crop extent do not overlap.")

    if any(shp.geometry.type == "MultiPoint"):
        return _clip_multi_point(shp, clip_obj)
    elif any(shp.geometry.type == "Point"):
        return _clip_points(shp, clip_obj)
    elif any(shp.geometry.type == "MultiPolygon") or any(
        shp.geometry.type == "MultiLineString"
    ):
        return _clip_multi_poly_line(shp, clip_obj)
    else:
        return _clip_line_poly(shp, clip_obj)


####################################################
# convert rectangle to shapefile
#
# save_clip_to_bbox(path,geom,minx,maxx,miny,maxy,dst_crs)
# Args:
# path path to shapefile output
# geom NOT USED
# minx,maxx,miny,maxy coordinates of bounding box
# dst_crs Coordinate Refernce System
####################################################


def save_clip_to_bbox(path, geom, minx, maxx, miny, maxy, dst_crs):
    y_point_list = [miny, miny, maxy, maxy, miny]
    x_point_list = [minx, maxx, maxx, minx, minx]

    bbox_geom = Polygon(zip(x_point_list, y_point_list))

    polygo = gpd.GeoDataFrame(index=[0], crs=dst_crs, geometry=[bbox_geom])

    clipped = clip_shp(geom, polygo)
    clipped.to_file(path)


try:
    import httplib
except Exception:
    import http.client as httplib

####################################################
# determine if http access is available for a URL
# have_access(URL)
# Args:
# url URL of site to test
# Determines if network access to URL is available, returns Boolean
####################################################


def have_access(url):
    conn = httplib.HTTPConnection(url, timeout=5)
    try:
        conn.request("HEAD", "/")
        conn.close()
        print("available: " + url)
        return True
    except Exception:
        conn.close()
        print("NOT available: " + url)
        return False


####################################################
# calculate 3D direction cosines from dip, dipdirection
#
# ddd2dircos(dip,dipdir)
# Args:
# dip dip of bedding from horizontal
# dipdir clockwise degrees from North of dip direction
# Returns:
# l,m,n direction cosines of pole to plane
#
# Converts dip, dip direction to three direction cosine arrays(l,m,n)
####################################################


def ddd2dircos(dip, dipdir):
    l = sin(radians(float(dipdir))) * cos(radians(90 - float(dip)))
    m = cos(radians(float(dipdir))) * cos(radians(90 - float(dip)))
    n = sin(radians(90 - float(dip)))
    return (l, m, n)


####################################################
# calculate dip, dipdirection from 3D direction cosines
#
# dircos2ddd(l,m,n)
# Args:
# l,m,n direction cosines of pole to plane Returns: dip dip of bedding from horizontal
# dipdir clockwise degrees from North of dip direction
#
# Converts (l,m,n) direction cosine arrays to dip, dip direction
####################################################


def dircos2ddd(l, m, n):
    dipdir = degrees(atan2(l, m)) % 360
    dip = 90 - degrees(asin(n))
    if dip > 90:
        dip = 180 - dip
        dipdir = dipdir + 180
    dipdir = dipdir % 360

    return (dip, dipdir)


####################################################
# Calulate 2D direction cosines from two points
#
# pts2dircos(p1x,p1y,p2x,p2y)
# Args:
# p1x,p1y a point
# p2x,p2y another point
# Returns:
# l,m 2D direction cosines of line segment
#
# Returns l,m direction cosines of line segment defined by points
####################################################


def pts2dircos(p1x, p1y, p2x, p2y):
    dlsx = p1x - p2x
    dlsy = p1y - p2y
    if p1x == p2x and p1y == p2y:
        return (0, 0)
    l = dlsx / sqrt((dlsx * dlsx) + (dlsy * dlsy))
    m = dlsy / sqrt((dlsx * dlsx) + (dlsy * dlsy))
    return (l, m)


####################################################
# calculate distance between two points
# duplicated in m2l_geometry, don't know why!
#
# Args:
# p1x,p1y a point
# p2x,p2y another point
# Calculates distance between two points
####################################################


def ptsdist(p1x, p1y, p2x, p2y):
    dist = sqrt(pow(p1x - p2x, 2) + pow(p1y - p2y, 2))
    return dist


###########################################
# Apical angle between three points, first point is at apex
#
# Args:
# p1x,p1y apical point
# p2x,p2y another point
# p3x,p3y a third point
#
# Caluclates angle of three points
###########################################


def tri_angle(p1x, p1y, p2x, p2y, p3x, p3y):
    p12 = ptsdist(p1x, p1y, p2x, p2y)
    p13 = ptsdist(p1x, p1y, p3x, p3y)
    p23 = ptsdist(p2x, p2y, p3x, p3y)

    numerator = pow(p12, 2.0) + pow(p13, 2.0) - pow(p23, 2.0)
    divisor = 2 * p12 * p13

    if fabs(numerator / divisor) > 1.0:
        angle = 180.0
    else:
        angle = degrees(acos(numerator / divisor))

    return angle


###########################################
# plot_points on map
###########################################


def plot_points(
    point_source, geol_clip, colour_code, x_code, y_code, legend, dtype, title
):
    from shapely.geometry import Point
    import matplotlib.pyplot as plt

    thick = pd.read_csv(point_source, encoding="ISO-8859-1", dtype="object")
    if dtype == "numeric":
        thick["cc"] = pd.to_numeric(thick[colour_code])
    else:
        thick["cc"] = thick[colour_code]
    thick[x_code] = thick[x_code].astype("float64")
    thick[y_code] = thick[y_code].astype("float64")
    thick = gpd.GeoDataFrame(
        thick, geometry=[Point(xy) for xy in zip(thick[x_code], thick[y_code])]
    )
    base = geol_clip.plot(
        color="white", figsize=(7, 7), edgecolor="#000000", linewidth=0.2
    )
    plot2 = thick.plot(
        ax=base, column="cc", markersize=15, cmap="rainbow", legend=legend
    )
    plot2 = plot2.figure
    plot2.tight_layout()
    plt.title(title)
    plt.show()


###########################################
# plot bedding stereonets
###########################################


def plot_bedding_stereonets(config, map_data):
    import mplstereonet
    import matplotlib.pyplot as plt

    # orientations = gpd.sjoin(orientations_clean, geology, how="left", predicate="within")
    geology = map_data.get_map_data(Datatype.GEOLOGY)
    # TODO: orientations should be 'clean'
    orientations = map_data.get_map_data(Datatype.STRUCTURE).copy()
    is_bed = orientations["STRUCTURE_TYPE"].str.contains(
        config.c_l["bedding"], regex=False
    )

    orientations = orientations[is_bed]
    groups = geology["GROUP"].unique()
    codes = geology["UNIT_NAME"].unique()
    if config.verbose_level != VerboseLevel.NONE:
        print("All observations n=", len(orientations))
        print("groups", groups, "\ncodes", codes)

    # As map_checker converts to dip direction assume orientations are in dip dir
    strikes = orientations["DIPDIR"].values.astype(float) - 90

    if config.verbose_level != VerboseLevel.NONE:
        fig, ax = mplstereonet.subplots(figsize=(7, 7))
        dips = orientations["DIP"].values.astype(float)
        ax.density_contourf(strikes, dips, measurement="poles")
        ax.pole(strikes, dips, markersize=5, color="w")
        ax.grid(True)
        # text = ax.text(2.2, 1.37, "All data", color='b')
        plt.title("All data")
        plt.show()
    group_girdle = {}
    for gp in groups:
        all_orientations = orientations[orientations["GROUP"] == gp]
        if len(all_orientations) == 1:
            group_girdle[gp] = (-999, -999, 1)

            if config.verbose_level != VerboseLevel.NONE:
                print(
                    "----------------------------------------------------------------------------------------------------------------------"
                )
                print(gp, "observations has 1 observation")

        elif len(all_orientations) > 0:

            ax = None

            # As map_checker converts to dip direction assume orientations are in dip dir
            strikes = all_orientations["DIPDIR"].values.astype(float) - 90

            dips = all_orientations["DIP"].values.astype(float)
            fit_strike, fit_dip = mplstereonet.fit_girdle(strikes, dips)
            (plunge,), (bearing,) = mplstereonet.pole2plunge_bearing(
                fit_strike, fit_dip
            )
            group_girdle[gp] = (plunge, bearing, len(all_orientations))

            if config.verbose_level != VerboseLevel.NONE:
                print(
                    "----------------------------------------------------------------------------------------------------------------------"
                )
                print(gp, "observations n=", len(all_orientations))
                print("strike/dip of girdle", fit_strike, "/", fit_dip)
            if config.verbose_level == VerboseLevel.ALL:
                fig, ax = mplstereonet.subplots(figsize=(5, 5))
                ax.density_contourf(strikes, dips, measurement="poles")
                ax.pole(strikes, dips, markersize=5, color="w")
                ax.grid(True)
                # text = ax.text(2.2, 1.37, gp, color='b')
                plt.title(gp)
                plt.show()
        else:
            group_girdle[gp] = (-999, -999, 0)

            if config.verbose_level != VerboseLevel.NONE:
                print(
                    "----------------------------------------------------------------------------------------------------------------------"
                )
                print(gp, "observations has no observations")

    return group_girdle


@beartype.beartype
def plot_bedding_stereonets_old(orientations, all_sorts, verbose_level: VerboseLevel):
    import mplstereonet
    import matplotlib.pyplot as plt

    groups = all_sorts["group"].unique()
    if verbose_level != VerboseLevel.NONE:
        print("All observations n=", len(orientations))

    if verbose_level == VerboseLevel.ALL:
        fig, ax = mplstereonet.subplots(figsize=(7, 7))
        strikes = orientations["azimuth"].values - 90
        dips = orientations["dip"].values
        ax.density_contourf(strikes, dips, measurement="poles")
        ax.pole(strikes, dips, markersize=5, color="w")
        ax.grid(True)
        # text = ax.text(2.2, 1.37, "All data", color='b')
        plt.title("All Data")
        plt.show()

    for gp in groups:
        all_sorts2 = all_sorts[all_sorts["group"] == gp]
        all_sorts2.set_index("code", inplace=True)

        first = True
        for indx, as2 in all_sorts2.iterrows():
            orientations2 = orientations[orientations["formation"] == indx]
            if first:
                first = False
                all_orientations = orientations2.copy()
            else:
                all_orientations = pd.concat(
                    [all_orientations, orientations2], sort=False
                )

        if len(all_orientations) > 0:
            if verbose_level != VerboseLevel.NONE:
                print(
                    "----------------------------------------------------------------------------------------------------------------------"
                )
                print(gp, "observations n=", len(all_orientations))
            if verbose_level == VerboseLevel.ALL:
                fig, ax = mplstereonet.subplots(figsize=(5, 5))
                strikes = all_orientations["azimuth"].values - 90
                dips = all_orientations["dip"].values
                ax.density_contourf(strikes, dips, measurement="poles")
                ax.pole(strikes, dips, markersize=5, color="w")
                ax.grid(True)
                ax.text(2.2, 1.37, gp, color="b")
                plt.title(gp)
                plt.show()

    for gp in groups:
        all_sorts2 = all_sorts[all_sorts["group"] == gp]
        all_sorts2.set_index("code", inplace=True)

        if verbose_level != VerboseLevel.NONE:
            print(
                "----------------------------------------------------------------------------------------------------------------------"
            )
            print(gp)
        ind = 0

        for indx, as2 in all_sorts2.iterrows():
            ind2 = int(fmod(ind, 3))
            orientations2 = orientations[orientations["formation"] == indx]
            if verbose_level != VerboseLevel.NONE:
                print(indx, "observations n=", len(orientations2))
            if verbose_level == VerboseLevel.ALL:
                if len(orientations2) > 0:
                    if ind2 == 0:
                        fig, ax = mplstereonet.subplots(1, 3, figsize=(15, 15))
                    strikes = orientations2["azimuth"].values - 90
                    dips = orientations2["dip"].values

                    ax[ind2].density_contourf(strikes, dips, measurement="poles")
                    ax[ind2].pole(strikes, dips, markersize=5, color="w")
                    ax[ind2].grid(True)
                    # fig.colorbar(cax)
                    ax[ind2].text(2.2, 1.37, indx, color="b")

                    # Fit a plane to the girdle of the distribution and display it.
                    fit_strike, fit_dip = mplstereonet.fit_girdle(strikes, dips)
                    print("strike/dip of girdle", fit_strike, "/", fit_dip)

                    if ind2 == 2:
                        plt.show()

                    ind = ind + 1

        if ind > 0 and not ind2 == 2 and verbose_level == VerboseLevel.ALL:
            plt.show()


def hextofloats(h):
    """Takes a hex rgb string (e.g. #ffffff) and returns an RGB tuple (float, float, float)."""
    return tuple(int(h[i : i + 2], 16) / 255.0 for i in (1, 3, 5))  # skip '#'


def floatstohex(rgb):
    """Takes an RGB tuple or list and returns a hex RGB string."""
    return f"#{int(rgb[0]*255):02x}{int(rgb[1]*255):02x}{int(rgb[2]*255):02x}"


def hextoints(h):
    """Takes a hex rgb string (e.g. #ffffff) and returns an RGB tuple (float, float, float)."""
    return tuple(int(h[i : i + 2], 16) for i in (1, 3, 5))


def intstohex(rgb):
    """Takes an RGB tuple or list and returns a hex RGB string."""
    return f"#{int(rgb[0]):02x}{int(rgb[1]):02x}{int(rgb[2]):02x}"


def display(element):
    if "IPython" in sys.modules:
        import IPython

        try:
            from IPython import get_ipython
            from IPython.display import display, Image, HTML

            IPython.display(element)
        except Exception:
            return False


def save_dtm_mesh(dtm_path, output_path):
    import rasterio

    path_in = dtm_path + "/dtm_rp.tif"
    dtm = rasterio.open(path_in)
    band1 = dtm.read(1)
    pixel = (dtm.bounds.right - dtm.bounds.left) / band1.shape[1]
    band1 = band1.T
    band1.shape
    f = []  # faces
    v = []  # vertices

    for x in range(10, band1.shape[0] - 10):
        for y in range(10, band1.shape[1] - 10):
            v.append(
                [
                    "v",
                    dtm.bounds.left + x * pixel,
                    dtm.bounds.top - y * pixel,
                    band1[x, y],
                ]
            )

    for y in range(10, band1.shape[1] - 11):
        for x in range(10, band1.shape[0] - 11):
            i = y + 1 + ((x - 10) * (band1.shape[1] - 20)) - 10
            # if(band1[x,y]>-10000 and band1[x+1,y]>-10000 and band1[x,y+1]>-10000 ):
            f.append(["f", i, i + 1, i + band1.shape[1] - 20])
            # if(band1[x+1,y]>-10000 and band1[x+1,y+1]>-10000 and band1[x,y+1]>-10000 ):
            f.append(["f", i + 1, i + band1.shape[1] - 19, i + band1.shape[1] - 20])

    file = open(output_path + "/dtm.obj", "w")
    for pts in v:
        file.write(" ".join(map(str, pts)) + "\n")
    for ind in f:
        file.write(" ".join(map(str, ind)) + "\n")
    file.close()


def save_dtm_ascii(dtm_path):
    dtm_file = os.path.join(dtm_path, "dtm_rp.tif")
    with rasterio.open(dtm_file) as dtm:
        band1 = dtm.read(1)
        pixelx = (dtm.bounds.right - dtm.bounds.left) / band1.shape[1]
        pixely = (dtm.bounds.top - dtm.bounds.bottom) / band1.shape[0]
        with open(os.path.join(dtm_path, "dtm_rp.hdr"), "w") as header:
            header.write(
                "{},{},{},{}\n".format(pixelx, pixely, band1.shape[0], band1.shape[1])
            )
            header.write(
                "{},{},{},{}\n".format(
                    dtm.bounds.left, dtm.bounds.bottom, dtm.bounds.right, dtm.bounds.top
                )
            )
        band1 = band1.T

        band1.tofile(os.path.join(dtm_path, "dtm_rp.csv"), sep=",")


def save_parameters(
    model_name, vtk_model_path, proj, foliation_params, fault_params, st_bbox, m2lv, LSv
):

    f = open(os.path.join(vtk_model_path, "params.txt"), "w")

    f.write("map2loop version: " + m2lv + "\n")
    f.write("LoopStructural version: " + LSv + "\n")
    f.write("model_name: " + model_name + "\n")
    f.write("project_path: " + str(proj.config.project_path) + "\n")
    f.write("c_l: " + str(proj.config.c_l).replace("),", "),\n") + "\n")
    f.write("run_flags: " + str(proj.config.run_flags).replace(", '", ",\n'") + "\n")
    f.write("workflow: " + str(proj.workflow).replace(", '", ",\n'") + "\n")
    f.write("bbox_LL: " + str(st_bbox) + "\n")
    f.write("bbox_3d: " + str(proj.config.bbox_3d) + "\n")
    f.write("proj_crs: " + str(proj.map_data.working_projection) + "\n")
    f.write(
        "geology_layer: " + str(proj.map_data.get_filename(Datatype.GEOLOGY)) + "\n"
    )
    f.write("dtm_layer: " + str(proj.map_data.get_filename(Datatype.DTM)) + "\n")
    f.write("fault_layer: " + str(proj.map_data.get_filename(Datatype.FAULT)) + "\n")
    f.write("fold_layer: " + str(proj.map_data.get_filename(Datatype.FOLD)) + "\n")
    f.write(
        "structure_layer: " + str(proj.map_data.get_filename(Datatype.STRUCTURE)) + "\n"
    )
    f.write(
        "mindep_layer: "
        + str(proj.map_data.get_filename(Datatype.MINERAL_DEPOSIT))
        + "\n"
    )
    f.write(
        "section_layer: " + str(proj.map_data.get_filename(Datatype.SECTION)) + "\n"
    )
    f.write(
        "drillhole_layer: " + str(proj.map_data.get_filename(Datatype.DRILLHOLE)) + "\n"
    )
    f.write(
        "dtb_grid_layer: " + str(proj.map_data.get_filename(Datatype.DTB_GRID)) + "\n"
    )
    f.write(
        "cover_map_layer: " + str(proj.map_data.get_filename(Datatype.COVER_MAP)) + "\n"
    )
    f.write("fault_params: " + str(fault_params) + "\n")
    f.write("foliation_params: " + str(foliation_params) + "\n")
    f.close()


timer_decorator_enabled = False


def timer_decorator(func):
    @functools.wraps(func)
    def decorator(*args, **kwargs):
        print(f"Entering function {func.__name__}")
        starttime = time.time()
        func(*args, **kwargs)
        runtime = time.time() - starttime
        print(f"Function {func.__name__} took {runtime:.4f} seconds")

    def clean(*args, **kwargs):
        return func(*args, **kwargs)

    if timer_decorator_enabled:
        return decorator
    else:
        return clean
