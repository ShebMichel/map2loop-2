from shapely.geometry import (
    Polygon,
    MultiLineString,
    LineString,
    Point,
    MultiPolygon,
)
import geopandas as gpd
import pandas as pd
from math import (
    acos,
    sqrt,
    cos,
    sin,
    degrees,
    radians,
    fabs,
    atan2,
    fmod,
    isnan,
    atan,
    asin,
)
from . import m2l_utils

from . import m2l_interpolation
import numpy as np
import os
import random
import networkx as nx
import statistics
from shapely.ops import snap
import beartype
from .m2l_enums import Datatype, VerboseLevel
from .config import Config
from .mapdata import MapData
from osgeo import ogr
from shapely.wkt import loads

####################################################
# Export orientation data in csv format with heights and strat code added
#
# save_orientations(structure_code,output_path,c_l,orientation_decimate,dtm)
# Args:
# structure_code geopandas point layer
# output_path directory of outputs from m2lc
# c_l dictionary of codes and labels specific to input geo information layers
# decimate saves every nth orientation point (without reference to spatial density or structural complexity)
# dtm rasterio format georeferenced dtm grid
#
# Save dip,dip direction of bedding extracted from geology layer with additional height information from dtm and joined with
# polygon information from geology polygon layer. Stored as csv file.
# Orientation data needs calculated height as file does not provide it, taken from SRTM data already downloaded.
# To calculate polarity (WHICH WE DON'T DO YET) we can calculate the dot product of the dip direction of a bedding plane
# and the vector to that points nearest basal contact node, if abs(acos(dot product))>90 then right way up.
####################################################


@beartype.beartype
def save_orientations(config: Config, map_data: MapData, workflow):
    """[Export orientation data in csv format with heights and strat code added]

    Args:
        structures ([geopandas DataFrame]): [point structural oberservations]
        path_out ([str]): [path to output directory]
        c_l ([type]): [description]
        orientation_decimate ([int]): [decimation factor]
        dtm ([rasterio grid]): [digital terrain model]
        dtb ([rasterio grid]): [depth to basement model]
        dtb_null ([float]): [null dtb value]
        cover_map ([boolean]): [availability of cover map]
    """
    structures = map_data.get_map_data(Datatype.STRUCTURE)
    dtm = map_data.get_map_data(Datatype.DTM).open()
    dtb = map_data.dtb
    dtb_null = map_data.dtb_null
    is_bed = structures["STRUCTURE_TYPE"].str.contains(
        config.c_l["bedding"], regex=False
    )

    structure_clip = structures[is_bed]
    # print(structure_clip.columns)
    i = 0
    f = open(os.path.join(config.output_path, "orientations.csv"), "w")
    f.write("X,Y,Z,azimuth,dip,polarity,formation\n")
    for indx, apoint in structure_clip.iterrows():
        if not str(apoint["ROCKTYPE1"]) == "None":
            if not str(apoint["ROCKTYPE1"]) == "nan":
                if not config.c_l["intrusive"] in apoint["ROCKTYPE1"]:
                    if (
                        apoint["DIP"] != 0
                        and i % config.run_flags["orientation_decimate"] == 0
                    ):
                        locations = [(apoint["geometry"].x, apoint["geometry"].y)]
                        if (
                            apoint["geometry"].x > dtm.bounds[0]
                            and apoint["geometry"].x < dtm.bounds[2]
                            and apoint["geometry"].y > dtm.bounds[1]
                            and apoint["geometry"].y < dtm.bounds[3]
                        ):
                            height = m2l_utils.value_from_dtm_dtb(
                                dtm, dtb, dtb_null, workflow["cover_map"], locations
                            )
                            dipdir = apoint["DIPDIR"]
                            if apoint["POLARITY"] != config.c_l["btype"]:
                                polarity = 1
                            else:
                                polarity = 0
                            ostr = "{},{},{},{},{},{},{}\n".format(
                                apoint["geometry"].x,
                                apoint["geometry"].y,
                                height,
                                dipdir,
                                apoint["DIP"],
                                polarity,
                                apoint["UNIT_NAME"].replace(" ", "_").replace("-", "_"),
                            )
                            # ostr = str(apoint['geometry'].x)+","+str(apoint['geometry'].y)+","+height+","+str(dipdir)+","+str(apoint['DIP'])+",1,"+str(apoint['UNIT_NAME'].replace(" ","_").replace("-","_"))+"\n"
                            f.write(ostr)
                    i = i + 1

    f.close()

    # try:
    if "sl" in config.c_l and config.c_l["sl"] != "None":
        sl_code_list = [
            "S1",
            "S2",
            "S3",
            "S4",
            "S5",
            "S0/S1",
            "S1/S2",
            "S2/S3",
            "S3/S4",
            "S4/S5",
            "F1",
            "F2",
            "F3",
            "F4",
            "F5",
        ]
        f = open(os.path.join(config.output_path, "secondary_orientations.csv"), "w")
        f.write("X,Y,Z,type,azimuth,dip,polarity,formation\n")
        for indx, apoint in structures.iterrows():
            if not str(apoint["ROCKTYPE1"]) == "None":
                if not str(apoint["ROCKTYPE1"]) == "nan":
                    if not config.c_l["intrusive"] in apoint["ROCKTYPE1"]:
                        if (
                            apoint["DIP"] != 0
                            and i % config.run_flags["orientation_decimate"] == 0
                        ):
                            locations = [(apoint["geometry"].x, apoint["geometry"].y)]
                            if (
                                apoint["geometry"].x > dtm.bounds[0]
                                and apoint["geometry"].x < dtm.bounds[2]
                                and apoint["geometry"].y > dtm.bounds[1]
                                and apoint["geometry"].y < dtm.bounds[3]
                            ):
                                height = m2l_utils.value_from_dtm_dtb(
                                    dtm, dtb, dtb_null, workflow["cover_map"], locations
                                )
                                dipdir = apoint["DIPDIR"]
                                polarity = 1
                                index = 0
                                sl_codes_test = config.c_l["sl_codes"].split(",")
                                sl_code_found = ""
                                for sli in sl_codes_test:
                                    # print(index,sli,apoint[config.c_l['sl']])
                                    if apoint["STRUCTURAL_LAYER"] == sli:
                                        sl_code_found = sl_code_list[index]
                                        # print(index,"apoint['STRUCTURAL_LAYER']",apoint['STRUCTURAL_LAYER'],"'STRUCTURAL_LAYER'",'STRUCTURAL_LAYER','sl_code_found',sl_code_found)
                                        break
                                    index = index + 1
                                if not sl_code_found == "":
                                    ostr = "{},{},{},{},{},{},{},{}\n".format(
                                        apoint["geometry"].x,
                                        apoint["geometry"].y,
                                        height,
                                        sl_code_found,
                                        dipdir,
                                        apoint["DIP"],
                                        polarity,
                                        apoint["UNIT_NAME"],
                                    )
                                    # ostr = str(apoint['geometry'].x)+","+str(apoint['geometry'].y)+","+height+","+str(dipdir)+","+str(apoint['DIP'])+",1,"+str(apoint['UNIT_NAME'].replace(" ","_").replace("-","_"))+"\n"
                                    f.write(ostr)
                        i = i + 1

        f.close()
    else:
        if config.verbose_level != VerboseLevel.NONE:
            print("no secondary structure data available")
    if config.verbose_level != VerboseLevel.NONE:
        print(
            i,
            "orientations saved to",
            os.path.join(config.output_path, "orientations.csv"),
        )


####################################################
# Find those series that don't have any orientation or contact point data and add some random data
# create_orientations(tmp_path, output_path, dtm,geol_clip,structure_clip,c_l)
# Args:
# tmp_path directory of temporary outputs
# output_path directory of outputs
# dtm rasterio format elevation grid
# geology geopandas layer of geology polygons
# structures geopandas layer of orientation points c_l dictionary of codes and labels specific to input geo information layers
# c_l dictionary of codes and labels specific to input geo information layers
#
# Save additional arbitrary dip/dip direction data for series/groups that don’t have structural information available.
# Ignores intrusive polygons. Somewhat superceded by interpolation codes. Could use dip direction normal to basal contact
# (if there is one) but don't do this yet.
####################################################


@beartype.beartype
def create_orientations(config: Config, map_data: MapData, workflow: dict):
    """[Find those series that don't have any orientation or contact point data and add some random data]

    Args:
        path_in ([str]): [path to input directory]
        path_out ([str]): [path to output directory]
        dtm ([rasterio grid]): [digital terrain model]
        dtb ([rasterio grid]): [depth to basement model]
        dtb_null ([float]): [null dtb value]
        cover_map ([boolean]): [availability of cover map]
        geology ([geopandas DataFrame]): [geology polygons]
        structures ([geopandas DataFrame]): [point structural oberservations]
        c_l ([dict]): [field names]
    """
    # Create orientations if there is a series that does not have one."
    # f = open(os.path.join(path_in,'groups.csv'),"r")
    # contents  = f.readlines()
    # f.close

    # ngroups = contents[0].split(" ")
    # ngroups = int(ngroups[1])
    contents = np.genfromtxt(
        os.path.join(config.tmp_path, "groups.csv"), delimiter=",", dtype="U100"
    )
    ngroups = len(contents[0]) - 1
    # print(len(contents[0]))
    groups = []
    for i in range(1, int(ngroups) + 1):
        # print(contents[0][i].replace("\n",""))
        groups.append((contents[0][i].replace("\n", ""), 0))

    # print(ngroups,groups)

    structures = map_data.get_map_data(Datatype.STRUCTURE)
    for i in range(1, ngroups):
        for indx, apoint in structures.iterrows():
            if str(apoint["GROUP"]) == "None":
                agroup = apoint["UNIT_NAME"]
            else:
                agroup = apoint["GROUP"]
            # print(agroup)
            if groups[i][0] == agroup:
                lgroups = list(groups[i])
                lgroups[1] = 1
                lgroups = tuple(lgroups)
                groups[i] = lgroups

    # print("Orientations----------\n",ngroups,groups)

    geology = map_data.get_map_data(Datatype.GEOLOGY)
    for i in range(0, ngroups):
        for indx, apoly in geology.iterrows():
            agroup = apoly["GROUP"]
            # print(agroup)
            if groups[i][0] == agroup:
                lgroups = list(groups[i])
                lgroups[1] = 1
                lgroups = tuple(lgroups)
                groups[i] = lgroups

    all_codes = []
    for ind, ageol in geology.iterrows():  # central polygon
        all_codes.append(ageol["UNIT_NAME"])

    # print("Contacts----------\n",len(set(all_codes)),set(all_codes))

    f = open(os.path.join(config.output_path, "empty_series_orientations.csv"), "w")
    f.write("X,Y,Z,azimuth,dip,polarity,formation\n")
    # f.write("X,Y,Z,DipDirection,dip,dippolarity,formation\n")

    dtm = map_data.get_map_data(Datatype.DTM).open()
    for i in range(0, ngroups):
        if groups[i][1] == 0:
            for indx, ageol in geology.iterrows():
                if (
                    ageol["UNIT_NAME"].replace("-", "_") == groups[i][0]
                    and groups[i][1] == 0
                    and not config.c_l["intrusive"] in ageol["ROCKTYPE1"]
                ):
                    apoly = Polygon(ageol["geometry"])
                    apoint = apoly.representative_point()
                    # print(apoint.x,apoint.y)
                    locations = [(apoint.x, apoint.y)]
                    height = m2l_utils.value_from_dtm_dtb(
                        dtm,
                        map_data.dtb,
                        map_data.dtb_null,
                        workflow["cover_map"],
                        locations,
                    )
                    if height == -999:
                        print("point off map", locations)
                        height = 0  # needs a better solution!
                    ostr = "{},{},{},{},{},{},{}\n".format(
                        apoint.x, apoint.y, height, 0, 45, 1, ageol["UNIT_NAME"]
                    )
                    # ostr = str(apoint.x)+","+str(apoint.y)+","+height+",0,45,1"+","+str(ageol['UNIT_NAME'])+"\n"
                    f.write(ostr)
                    # plt.title(str(ageol['UNIT_NAME']))
                    # plt.scatter(apoint.x,apoint.y,color = "red")
                    # plt.plot(*apoly.exterior.xy)
                    # plt.show()
                    break

    f.close()
    if config.verbose_level != VerboseLevel.NONE:
        print(
            "extra orientations saved as",
            os.path.join(config.output_path, "/empty_series_orientations.csv"),
        )


####################################################
# Convert polygons with holes into distinct poygons
# modified from https://stackoverflow.com/questions/21824157/how-to-extract-interior-polygon-coordinates-using-shapely
#
# extract_poly_coords(part,i)
# Args:
# part shapely format polygon or multipolygon with or without interior holes
# i counter for distict interior/exterior polylines
# Returns:
# exterior_coords exterior coordinates of ploygon interior_coords array of interior hole's interior coordinates
#
# Shapely multgipolygons can contain interior holes which need to be extracted as distinct contact polylines
# for use in map2loop. This code achieves that.
####################################################


def extract_poly_coords(geom, i):
    """[Convert polygons with holes into distinct poygons]

    Args:
        geom ([shapely geometry]): [geology polygon or multipolygon]
        i ([int]): [master index of polygon coordinates]

    Raises:
        ValueError: [geometry type if not a polygon or multipolygon]

    Returns:
        [dict]: [exterior and interior coordinates]
    """
    if geom.type == "Polygon":
        exterior_coords = geom.exterior.coords[:]
        interior_coords = []
        for interior in geom.interiors:
            interior_coords += (i, interior.coords[:])
            i = i + 1

    elif geom.type == "MultiPolygon":
        exterior_coords = []
        interior_coords = []
        for part in geom.geoms:
            epc = extract_poly_coords(part, i)  # Recursive call
            exterior_coords += epc["exterior_coords"]
            interior_coords += epc["interior_coords"]
            i = i + 1
    else:
        raise ValueError("Unhandled geometry type: " + repr(geom.type))
    return {"exterior_coords": exterior_coords, "interior_coords": interior_coords}


####################################################
# extract stratigraphically lower contacts from geology polygons and save as points
#
# save_basal_contacts(tmp_path,dtm,geol_clip,contact_decimate,c_l,intrusion_mode)
# Args:
# tmp_path directory of temporary outputs
# dtm rasterio format elevation grid
# geol_clip geopandas layer of clipped geology polygons
# contact_decimate decimation factor for saving every nth input point on contact polylines
# c_l dictionary of codes and labels specific to input geo information layers
# intrusion_mode Boolean for saving intrusive contacts or not
# Returns:
# dictionaries of basal contacts with and without decimation.
#
# Saves a shapefile of the basal contacts of each stratigraphic unit (but not intrusives). This analysis uses
# the relative age of each unit, and includes faulted contacts, that are filtered out by another function.
# Orientation data needs calculated height as file does not provide it, taken from SRTM data already downloaded.
# Need to reduce number of points whilst retaining useful info (Ranee's job!)' To calculate which are the basal units
# contact for a polygon find the polygons which are older than the selected polygon
# If there are no older units for a polygon it has no basal contact. We keep every nth node based on the decimate term
# (simple count along polyline). gempy seems to need at least two points per surface, so we always take the first two points.
####################################################


@beartype.beartype
def save_basal_contacts(
    config: Config, map_data: MapData, workflow: dict
) -> gpd.GeoDataFrame:
    # dissolve geometry into a single unit for rows with the same unit name
    geology = map_data.get_map_data(Datatype.GEOLOGY).copy()
    # Remove intrusions for geology
    geology = geology[~geology["ROCKTYPE1"].str.contains(config.c_l["intrusive"])]
    geology = geology.dissolve(by="UNIT_NAME", as_index=False)
    units = geology["UNIT_NAME"].unique()
    column_names = ["UNIT_NAME_1", "UNIT_NAME_2", "geometry"]
    contacts = gpd.GeoDataFrame(crs=geology.crs, columns=column_names, data=None)
    while len(units) > 1:
        unit1 = units[0]
        units = units[1:]
        for unit2 in units:
            if unit1 != unit2:
                join = gpd.overlay(
                    geology[geology["UNIT_NAME"] == unit1],
                    geology[geology["UNIT_NAME"] == unit2],
                    keep_geom_type=False,
                )[column_names]
                join["geometry"] = join.buffer(1)
                buffered = geology[geology["UNIT_NAME"] == unit2][["geometry"]].copy()
                buffered["geometry"] = buffered.boundary
                end = gpd.overlay(buffered, join, keep_geom_type=False)
                if len(end):
                    contacts = pd.concat([contacts, end], ignore_index=True)

    # get stratigraphic column from (all_sorts.csv)
    units = pd.read_csv(os.path.join(config.tmp_path, "all_sorts.csv"))["code"].tolist()
    groups = pd.read_csv(os.path.join(config.tmp_path, "all_sorts.csv"))[
        "group"
    ].tolist()

    # assign contact as basal based on its location in the column
    # also if it's adjacent indicate it's a basal contact otherwise indicate it
    # has skipped a unit with the abnormal contact type
    basal_contacts = contacts.copy()
    basal_contacts["ID"] = basal_contacts.apply(
        lambda row: min(
            units.index(row["UNIT_NAME_1"]),
            units.index(row["UNIT_NAME_2"]),
        ),
        axis=1,
    )
    basal_contacts["UNIT_NAME"] = basal_contacts.apply(
        lambda row: units[row["ID"]], axis=1
    )
    basal_contacts["GROUP"] = basal_contacts.apply(
        lambda row: groups[row["ID"]], axis=1
    )
    basal_contacts["distance"] = basal_contacts.apply(
        lambda row: abs(
            units.index(row["UNIT_NAME_1"]) - units.index(row["UNIT_NAME_2"])
        ),
        axis=1,
    )
    basal_contacts["type"] = basal_contacts.apply(
        lambda row: "ABNORMAL" if abs(row["distance"]) > 1 else "BASAL", axis=1
    )
    basal_contacts = basal_contacts[["geometry", "ID", "UNIT_NAME", "GROUP", "type"]]

    # # sample points along the boundary of polygons or lines
    # spacing = 250
    # schema = {"ID": str, "X": float, "Y": float}
    # df = pd.DataFrame(columns=schema.keys()).astype(schema)
    # for _, row in basal_contacts.iterrows():
    #     if type(row.geometry) == MultiPolygon:
    #         targets = row.geometry.boundary.geoms
    #     elif type(row.geometry) == Polygon:
    #         targets = [row.geometry.boundary]
    #     elif type(row.geometry) == MultiLineString:
    #         targets = row.geometry.geoms
    #     elif type(row.geometry) == LineString:
    #         targets = [row.geometry]
    #     else:
    #         targets = []

    #     # For the main cases Polygon and LineString the list 'targets' has one element
    #     for target in targets:
    #         df2 = pd.DataFrame(columns=schema.keys()).astype(schema)
    #         distances = np.arange(0, target.length, spacing)[:-1]
    #         points = [target.interpolate(distance) for distance in distances]
    #         df2["X"] = [point.x for point in points]
    #         df2["Y"] = [point.y for point in points]
    #         df2["ID"] = row["ID"]
    #         df2["GROUP"] = row["GROUP"]
    #         df2["CODE"] = row["UNIT_NAME"]
    #         df = pd.concat([df, df2])
    # df.reset_index(drop=True, inplace=True)

    # # get "Z" height value for contact points
    # dtm = map_data.get_map_data(Datatype.DTM).open()
    # df["Z"] = df.apply(
    #     lambda row: m2l_utils.value_from_dtm_dtb(
    #         dtm,
    #         map_data.dtb,
    #         map_data.dtb_null,
    #         workflow["cover_map"],
    #         [(row["X"], row["Y"])],
    #     ),
    #     axis=1,
    # )

    # # decimate by config.run_flags["contact_decimate"] for contacts output
    # decimate_value = max(1, config.run_flags["contact_decimate"])
    # decimated_contacts = df.iloc[::decimate_value].copy()

    # # Setup output (all_contacts.csv, contacts.csv)
    # decimated_contacts.rename(columns={"CODE": "formation"}, inplace=True)
    # decimated_contacts[["X", "Y", "Z", "formation"]].to_csv(
    #     os.path.join(config.tmp_path, "contacts.csv")
    # )
    # df.rename(
    #     columns={
    #         "GROUP": "GROUP_",
    #         "ID": "id",
    #         "X": "x",
    #         "Y": "y",
    #         "Z": "z",
    #         "CODE": "code",
    #     },
    #     inplace=True,
    # )
    # df[["GROUP_", "id", "x", "y", "z", "code"]].to_csv(
    #     os.path.join(config.tmp_path, "all_contacts.csv")
    # )

    return basal_contacts


#########################################
# Remove all basal contacts that are defined by faults and save to shapefile (no decimation)
#
# save_basal_no_faults(path_out,path_fault,ls_dict,dist_buffer,c_l,dst_crs)
# Args:
# path_out directory of output csv file
# path_fault path to clipped fault layer
# ls_dict dictionary of basal contact points
# dist_buffer distance in projection units of buffer around faults to clip
# c_l dictionary of codes and labels specific to input geo information layers
# dst_crs Coordinate Reference System of destination geotif (any length-based projection)
#
# Saves out a csv file of decimated basal contacts with height and formation information.
#########################################


@beartype.beartype
def save_basal_no_faults(config: Config, map_data: MapData) -> gpd.GeoDataFrame:
    output_filename = os.path.join(config.tmp_path, "basal_contacts.shp.zip")
    faults = map_data.get_map_data(Datatype.FAULT)
    contacts = map_data.basal_contacts
    if faults is not None:
        faults_clip_all = faults.copy()
        faults_clip = faults_clip_all[
            faults_clip_all["FEATURE"]
            .str.lower()
            .str.contains(config.c_l["fault"].lower())
        ]
        faults_clip = faults_clip.dropna(subset=["geometry"])

        # defines buffer around faults where strat nodes will be removed
        fault_zone = faults_clip.buffer(config.run_flags["dist_buffer"])
        all_fz = fault_zone.unary_union

        # deletes contact nodes within buffer
        contacts_nofaults = contacts.difference(all_fz)

        ls_nf = {}
        cnf_copy = contacts_nofaults.copy()

        # print(contacts_nofaults.shape)
        for i in range(0, len(contacts_nofaults)):
            j = len(contacts_nofaults) - i - 1
            # remove rows with geometry collections ( ==  empty?)
            if cnf_copy.iloc[j].geom_type == "GeometryCollection":
                cnf_copy.drop([j, j], inplace=True)
            else:  # save to dataframe
                ls_nf[j] = {
                    "id": j,
                    "UNIT_NAME": contacts.iloc[j]["UNIT_NAME"],
                    "GROUP": contacts.iloc[j]["GROUP"],
                    "geometry": cnf_copy.iloc[j],
                }

        df_nf = pd.DataFrame.from_dict(ls_nf, "index")

        contacts_nf = gpd.GeoDataFrame(
            df_nf, crs=map_data.working_projection, geometry="geometry"
        )
        contacts_nf.to_file(driver="ESRI Shapefile", filename=output_filename)

        if config.verbose_level != VerboseLevel.NONE:
            print("basal contacts without faults saved as", output_filename)
    else:
        contacts.to_file(driver="ESRI Shapefile", filename=output_filename)
        if config.verbose_level != VerboseLevel.NONE:
            print("basal contacts without faults saved as", output_filename)
    basal_contacts = gpd.read_file(output_filename)
    return basal_contacts


#########################################
# Save basal contacts from shapefile with decimation
#
# Args:
# contacts geopandas object containing basal contact polylines
# output_path directory of output csv file
# dtm rasterio format elevation grid
# contact_decimate decimation factor for saving every nth input point on contact polylines
#
#########################################


@beartype.beartype
def save_basal_contacts_csv(
    contacts: gpd.GeoDataFrame, config: Config, map_data: MapData, workflow: dict
):
    # sample points along the boundary of polygons or lines
    spacing = 250
    schema = {"ID": str, "X": float, "Y": float}
    df = pd.DataFrame(columns=schema.keys()).astype(schema)
    for _, row in contacts.iterrows():
        if type(row.geometry) == MultiPolygon:
            targets = row.geometry.boundary.geoms
        elif type(row.geometry) == Polygon:
            targets = [row.geometry.boundary]
        elif type(row.geometry) == MultiLineString:
            targets = row.geometry.geoms
        elif type(row.geometry) == LineString:
            targets = [row.geometry]
        else:
            targets = []

        # For the main cases Polygon and LineString the list 'targets' has one element
        for target in targets:
            df2 = pd.DataFrame(columns=schema.keys()).astype(schema)
            distances = np.arange(0, target.length, spacing)[:-1]
            points = [target.interpolate(distance) for distance in distances]
            df2["X"] = [point.x for point in points]
            df2["Y"] = [point.y for point in points]
            # df2["ID"] = row["ID"]
            df2["GROUP"] = row["GROUP"]
            df2["UNIT_NAME"] = row["UNIT_NAME"]
            df = pd.concat([df, df2])
    df.reset_index(drop=True, inplace=True)

    # get "Z" height value for contact points
    dtm = map_data.get_map_data(Datatype.DTM).open()
    df["Z"] = df.apply(
        lambda row: m2l_utils.value_from_dtm_dtb(
            dtm,
            map_data.dtb,
            map_data.dtb_null,
            workflow["cover_map"],
            [(row["X"], row["Y"])],
        ),
        axis=1,
    )

    # decimate by config.run_flags["contact_decimate"] for contacts output
    decimate_value = max(1, config.run_flags["contact_decimate"])
    decimated_contacts = df.iloc[::decimate_value].copy()

    # Setup output (contacts4.csv)
    decimated_contacts.rename(columns={"UNIT_NAME": "formation"}, inplace=True)
    decimated_contacts[["X", "Y", "Z", "formation"]].to_csv(
        os.path.join(config.output_path, "contacts4.csv")
    )

    if config.verbose_level != VerboseLevel.NONE:
        print(
            "decimated contacts saved as",
            os.path.join(config.output_path, "contacts4.csv"),
        )


#########################################
# Remove faults from decimated basal contacts as save as csv file   (superceded by save_basal_contacts_csv)
#
# save_contacts_with_faults_removed(path_fault,path_out,dist_buffer,ls_dict,ls_dict_decimate,c_l,dst_crs,dtm)
# Args:
# path_fault path to clipped fault layer
# path_out directory of output csv file
# dist_buffer distance in projection units of buffer around faults to clip
# ls_dict dictionary of basal contact points
# ls_dict dictionary of decimated basal contact points
# c_l dictionary of codes and labels specific to input geo information layers
# dst_crs Coordinate Reference System of destination geotif (any length-based projection)
# dtm rasterio format elevation grid
#
# Saves out csv file of basal contacts after clipping out buffered fault locations.
#########################################


def save_contacts_with_faults_removed(
    path_fault,
    path_out,
    dist_buffer,
    ls_dict,
    ls_dict_decimate,
    c_l,
    dst_crs,
    dtm,
    dtb,
    dtb_null,
    cover_map,
):
    faults_clip = gpd.read_file(path_fault)

    # df = pd.DataFrame.from_dict(ls_dict, "index")
    # contacts = gpd.GeoDataFrame(df, crs=dst_crs, geometry="geometry")
    faults_clip = faults_clip.dropna(subset=["geometry"])

    # defines buffer around faults where strat nodes will be removed
    fault_zone = faults_clip.buffer(dist_buffer)
    all_fz = fault_zone.unary_union
    # display(all_fz)
    print("undecimated points:", len(ls_dict_decimate))
    df_nf = pd.DataFrame.from_dict(ls_dict_decimate, "index")

    contacts_nf_deci = gpd.GeoDataFrame(df_nf, crs=dst_crs, geometry="geometry")

    # contacts_decimate_nofaults  =  contacts_nf_deci.difference(all_fz) #deletes contact nodes within buffer

    contacts_decimate_nofaults = contacts_nf_deci[
        ~contacts_nf_deci.geometry.within(all_fz)
    ]

    # cnf_de_copy = contacts_decimate_nofaults.copy()

    ac = open(os.path.join(path_out, "contacts4.csv"), "w")
    ac.write("X,Y,Z,formation\n")
    i = 0
    for indx, cdn in contacts_decimate_nofaults.iterrows():
        if not cdn.geometry.geom_type == "GeometryCollection":
            # print(cdn.x,cdn.y)
            # doesn't like point right on edge?
            locations = [(cdn.geometry.x, cdn.geometry.y)]

            height = m2l_utils.value_from_dtm_dtb(
                dtm, dtb, dtb_null, cover_map, locations
            )
            ostr = "{},{},{},{}\n".format(
                cdn.geometry.x,
                cdn.geometry.y,
                height,
                cdn["UNIT_NAME"].replace(" ", "_").replace("-", "_"),
            )
            # ostr = str(cdn.geometry.x)+","+str(cdn.geometry.y)+","+height+","+str(cdn["UNIT_NAME"].replace(" ","_").replace("-","_"))+"\n"
            ac.write(ostr)

        i = i + 1
    ac.close()
    print(
        i, "decimated contact points saved as", os.path.join(path_out, "contacts4.csv")
    )


#########################################
# Save faults as contact info and make vertical (for the moment)
#
# save_faults(path_faults,path_fault_orientations,dtm,c_l,fault_decimate)
# Args:
# path_faults path to clipped fault layer
# path_fault_orientations directory for outputs
# dtm rasterio format elevation grid
# c_l dictionary of codes and labels specific to input geo information layers
# fault_decimate decimation factor for saving every nth input point on fault polylines
#
# Saves out csv file of fault locations after decimation. Also saves out nominal orientation data at mid point
# of each fault trace with strike parallel to start end point line and arbitrary vertical dip. Also saves out csv list
# of faults with their start-finish length that could be used for filtering which faults to include in model.
#########################################


@beartype.beartype
def save_faults(config: Config, map_data: MapData, workflow: dict):
    dtm = map_data.get_map_data(Datatype.DTM).open()
    faults = map_data.get_map_data(Datatype.FAULT)
    f = open(os.path.join(config.output_path, "faults.csv"), "w")
    f.write("X,Y,Z,formation\n")
    fo = open(os.path.join(config.output_path, "fault_orientations.csv"), "w")
    fo.write("X,Y,Z,DipDirection,dip,DipPolarity,formation\n")
    # fo.write("X,Y,Z,azimuth,dip,polarity,formation\n")
    fd = open(os.path.join(config.output_path, "fault_dimensions.csv"), "w")
    fd.write(
        "Fault,HorizontalRadius,VerticalRadius,InfluenceDistance,incLength,colour\n"
    )
    # fd.write("Fault_ID,strike,dip_direction,down_dip\n")
    if faults is not None:
        local_faults = faults.copy()
        local_faults = local_faults.dropna(subset=["geometry"])

        # convert text dips to equally spaced angles
        split = config.c_l["fdipest_vals"].split(",")
        fault_dip_choices = np.linspace(0, 90, len(split) + 1)
        dip_dirs = {
            "north": (0.0, 1.0),
            "northeast": (0.707, 0.707),
            "east": (1.0, 0.0),
            "southeast": (0.707, -0.707),
            "south": (0.0, -1.0),
            "southwest": (-0.707, -0.707),
            "west": (-1.0, 0.0),
            "northwest": (-0.707, 0.707),
            "North": (0.0, 1.0),
            "Northeast": (0.707, 0.707),
            "East": (1.0, 0.0),
            "Southeast": (0.707, -0.707),
            "South": (0.0, -1.0),
            "Southwest": (-0.707, -0.707),
            "West": (-1.0, 0.0),
            "Northwest": (-0.707, 0.707),
            "Unknown": (0.0, 1.0),
            "Vertical": (0.707, 0.707),
        }
        random.seed(1)
        for indx, flt in local_faults.iterrows():
            if config.c_l["fault"].lower() in flt["FEATURE"].lower():
                fault_name = "Fault_" + str(flt["GEOMETRY_OBJECT_ID"])
                # display(flt.geometry.type)
                if flt.geometry.type == "LineString":
                    flt_ls = LineString(flt.geometry)
                    dlsx = (
                        flt_ls.coords[0][0] - flt_ls.coords[len(flt_ls.coords) - 1][0]
                    )
                    dlsy = (
                        flt_ls.coords[0][1] - flt_ls.coords[len(flt_ls.coords) - 1][1]
                    )
                    strike = sqrt((dlsx * dlsx) + (dlsy * dlsy))
                    azimuth_fault = degrees(atan2(dlsy, -dlsx)) % 180
                    if strike > config.run_flags["min_fault_length"]:
                        i = 0
                        saved = 0
                        fault_dip = 90.0
                        # null specifc dip defined
                        # print(config.c_l['fdipdir_flag'] ,str(flt["DIPDIR"]), int(flt["DIP"]) , int(config.c_l['fdipnull']),str(flt["DIP_ESTIMATE"]),config.run_flags['fault_dip'])
                        if int(float(flt["DIP"])) == int(float(config.c_l["fdipnull"])):
                            # dip estimate defined
                            if not str(flt["DIP_ESTIMATE"]) == "-999":
                                i = 0
                                for choice in split:
                                    if flt["GEOMETRY_OBJECT_ID"] == "-1":
                                        print(choice)
                                    if choice == flt["DIP_ESTIMATE"]:
                                        fault_dip = int(fault_dip_choices[i + 1])
                                        if flt["GEOMETRY_OBJECT_ID"] == "-1":
                                            print("found_dip", fault_dip)
                                    i = i + 1
                            else:
                                if (
                                    flt["DIP"] == -999
                                    or config.run_flags["fault_dip"] == -999
                                ):  # random flag
                                    fault_dip = random.randint(60, 90)
                                else:
                                    fault_dip = config.run_flags["fault_dip"]
                        else:
                            # specific dip defined
                            fault_dip = int(float(flt["DIP"]))

                        # numeric dip direction defined
                        if config.c_l["fdipdir_flag"] == "num":
                            if pd.notna(flt["DIPDIR"]) and str(flt["DIPDIR"]) != "-999":
                                azimuth = flt["DIPDIR"]
                            else:
                                azimuth = azimuth_fault

                        # alpha dip direction defined or no numeric dd defined
                        elif (
                            flt["DIP"] == -999 or config.run_flags["fault_dip"] == -999
                        ):
                            # print('az_before',fault_name,azimuth_fault)
                            azimuth = (
                                azimuth_fault + (180 * random.randint(0, 1))
                            ) % 360
                            # print('az_after',fault_name,azimuth)
                            # TODO: Fix comparison of str version of two floats are comparing floats is very inaccurate
                            #       Also if this logic works 'lsx' is not defined at this point
                        elif (
                            not str(flt["DIPDIR"]) == "None"
                            and not str(float(flt["DIP"]))
                            == str(float(config.c_l["fdipnull"]))
                            and flt["DIPDIR"] != "-999"
                        ):
                            dotprod = degrees(
                                acos(
                                    (-dlsx * dip_dirs[flt["DIPDIR"]][0])
                                    + (dlsy * dip_dirs[flt["DIPDIR"]][1])
                                )
                            )
                            if dotprod > 45:
                                fault_dip = -fault_dip
                        else:
                            azimuth = azimuth_fault
                        # print("indx,azimuth,azimuth_fault,flt["DIPDIR"],pd.notna( flt["DIPDIR"]),fault_dip_var, c_l['fdipnull'],flt["DIP"]")
                        # print( indx,azimuth,azimuth_fault,flt["DIPDIR"],pd.notna( flt["DIPDIR"]),fault_dip_var, c_l['fdipnull'],flt["DIP"])
                        l, m, n = m2l_utils.ddd2dircos((90 - fault_dip), azimuth)
                        # print('fault_name,l,m,n,azimuth_fault,dip',fault_name,l,m,n,azimuth,fault_dip)
                        first = True
                        incLength = 0
                        for afs in flt_ls.coords:
                            if dlsx == 0.0 and dlsy == 0.0:
                                continue
                            lsx = dlsx / sqrt((dlsx * dlsx) + (dlsy * dlsy))
                            lsy = dlsy / sqrt((dlsx * dlsx) + (dlsy * dlsy))
                            # normal to line segment
                            # azimuth = degrees(atan2(lsy, -lsx)) % 180

                            # if(flt[config."GEOMETRY_OBJECT_ID"] == '-1'):
                            # print(flt[config."GEOMETRY_OBJECT_ID"],  int(flt["DIP"]), config.c_l['fdipnull'],str(flt["DIP_ESTIMATE"]))

                            if first:
                                incLength = 0
                                lastx = afs[0]
                                lasty = afs[1]
                                first = False
                            else:
                                incLength = incLength + m2l_utils.ptsdist(
                                    afs[0], afs[1], lastx, lasty
                                )
                                lastx = afs[0]
                                lasty = afs[1]
                                # print(fault_name,incLength)
                            # decimate to reduce number of points, but also take mid and end points of a series to keep some shape
                            if (
                                i % config.run_flags["fault_decimate"] == 0
                                or i == int((len(flt_ls.coords) - 1) / 2)
                                or i == len(flt_ls.coords) - 1
                            ):
                                if saved == 0:
                                    p1x = afs[0]
                                    p1y = afs[1]
                                elif saved == 1:
                                    p2x = afs[0]
                                    p2y = afs[1]
                                elif saved == 2:
                                    p3x = afs[0]
                                    p3y = afs[1]
                                    # avoids narrow angles in fault traces which geomodeller refuses to solve
                                    # should really split fault in two at apex, but life is too short
                                    if (
                                        m2l_utils.tri_angle(
                                            p2x, p2y, p1x, p1y, p3x, p3y
                                        )
                                        < 45.0
                                    ):
                                        break
                                elif saved > 2:
                                    p1x = p2x
                                    p1y = p2y
                                    p2x = p3x
                                    p2y = p3y
                                    p3x = afs[0]
                                    p3y = afs[1]
                                    # avoids narrow angles in fault traces which geomodeller refuses to solve
                                    # should really split fault in two at apex, but life is too short
                                    if (
                                        m2l_utils.tri_angle(
                                            p2x, p2y, p1x, p1y, p3x, p3y
                                        )
                                        < 45.0
                                    ):
                                        break
                                saved = saved + 1
                                locations = [(afs[0], afs[1])]
                                height = m2l_utils.value_from_dtm_dtb(
                                    dtm,
                                    map_data.dtb,
                                    map_data.dtb_null,
                                    workflow["cover_map"],
                                    locations,
                                )
                                # slightly randomise first and last points to avoid awkward quadruple junctions etc.
                                # if(i == 0 or i == len(flt_ls.coords)-1):
                                #    ostr = str(afs[0]+np.random.ranf())+","+str(afs[1]+np.random.ranf())+","+str(height)+","+fault_name+"\n"
                                # else:
                                ostr = "{},{},{},{}\n".format(
                                    afs[0], afs[1], height, fault_name
                                )
                                # ostr = str(afs[0])+","+str(afs[1])+","+str(height)+","+fault_name+"\n"
                                f.write(ostr)
                                # dip projection equivalent of surface fault
                                proj_scale = -(
                                    (config.bbox_3d["base"] - float(height)) / n
                                )
                                ostr = "{},{},{},{}\n".format(
                                    afs[0] + (l * proj_scale) + 1,
                                    afs[1] + (m * proj_scale) + 1,
                                    float(height) - (n * proj_scale) + 1,
                                    fault_name,
                                )
                                # ostr = str(afs[0])+","+str(afs[1])+","+str(height)+","+fault_name+"\n"
                                f.write(ostr)
                            i = i + 1

                        strike = strike * 1.25
                        r = random.randint(1, 256) - 1
                        g = random.randint(1, 256) - 1
                        b = random.randint(1, 256) - 1
                        hex_rgb = m2l_utils.intstohex((r, g, b))
                        ostr = "{},{},{},{},{},{}\n".format(
                            fault_name,
                            strike / 2,
                            strike / 2,
                            strike / 4.0,
                            incLength,
                            hex_rgb,
                        )
                        # ostr = fault_name+","+str(strike/2)+","+str(strike)+","+str(strike/4.0)+"\n"
                        fd.write(ostr)

                        locations = [
                            (
                                flt_ls.coords[int((len(afs) - 1) / 2)][0],
                                flt_ls.coords[int((len(afs) - 1) / 2)][1],
                            )
                        ]
                        height = m2l_utils.value_from_dtm_dtb(
                            dtm,
                            map_data.dtb,
                            map_data.dtb_null,
                            workflow["cover_map"],
                            locations,
                        )
                        ostr = "{},{},{},{},{},{},{}\n".format(
                            flt_ls.coords[int((len(flt_ls.coords) - 1) / 2)][0],
                            flt_ls.coords[int((len(flt_ls.coords) - 1) / 2)][1],
                            height,
                            azimuth,
                            fault_dip,
                            1,
                            fault_name,
                        )
                        # ostr = str(flt_ls.coords[int((len(flt_ls.coords)-1)/2)][0])+","+str(flt_ls.coords[int((len(flt_ls.coords)-1)/2)][1])+","+height+","+str(azimuth)+","+str(fault_dip)+",1,"+fault_name+"\n"
                        fo.write(ostr)

                        locations = [(flt_ls.coords[0][0], flt_ls.coords[0][1])]
                        height = m2l_utils.value_from_dtm_dtb(
                            dtm,
                            map_data.dtb,
                            map_data.dtb_null,
                            workflow["cover_map"],
                            locations,
                        )
                        ostr = "{},{},{},{},{},{},{}\n".format(
                            flt_ls.coords[0][0],
                            flt_ls.coords[0][1],
                            height,
                            azimuth,
                            fault_dip,
                            1,
                            fault_name,
                        )
                        # ostr = str(flt_ls.coords[int((len(flt_ls.coords)-1)/2)][0])+","+str(flt_ls.coords[int((len(flt_ls.coords)-1)/2)][1])+","+height+","+str(azimuth)+","+str(fault_dip)+",1,"+fault_name+"\n"
                        fo.write(ostr)

                        locations = [
                            (
                                flt_ls.coords[len(flt_ls.coords) - 1][0],
                                flt_ls.coords[len(flt_ls.coords) - 1][1],
                            )
                        ]
                        height = m2l_utils.value_from_dtm_dtb(
                            dtm,
                            map_data.dtb,
                            map_data.dtb_null,
                            workflow["cover_map"],
                            locations,
                        )
                        ostr = "{},{},{},{},{},{},{}\n".format(
                            flt_ls.coords[len(flt_ls.coords) - 1][0],
                            flt_ls.coords[len(flt_ls.coords) - 1][1],
                            height,
                            azimuth,
                            fault_dip,
                            1,
                            fault_name,
                        )
                        # ostr = str(flt_ls.coords[int((len(flt_ls.coords)-1)/2)][0])+","+str(flt_ls.coords[int((len(flt_ls.coords)-1)/2)][1])+","+height+","+str(azimuth)+","+str(fault_dip)+",1,"+fault_name+"\n"
                        fo.write(ostr)

                # shouldn't happen any more
                elif (
                    flt.geometry.type == "MultiLineString"
                    or flt.geometry.type == "GeometryCollection"
                ):
                    sum_strike = 0
                    first = True
                    for pline in flt.geometry:
                        flt_ls = LineString(pline)
                        dlsx = (
                            flt_ls.coords[0][0]
                            - flt_ls.coords[len(flt_ls.coords) - 1][0]
                        )
                        dlsy = (
                            flt_ls.coords[0][1]
                            - flt_ls.coords[len(flt_ls.coords) - 1][1]
                        )
                        sum_strike = sum_strike + sqrt((dlsx * dlsx) + (dlsy * dlsy))
                        r = random.randint(1, 256) - 1
                        g = random.randint(1, 256) - 1
                        b = random.randint(1, 256) - 1
                        if first:
                            firstx = flt_ls.coords[0][0]
                            firsty = flt_ls.coords[0][1]
                        lastx = flt_ls.coords[0][0]
                        lasty = flt_ls.coords[0][1]
                    ostr = "{},{},{},{},{},{}\n".format(
                        fault_name,
                        sum_strike / 2,
                        sum_strike,
                        sum_strike / 4.0,
                        incLength,
                        hex_rgb,
                    )
                    # ostr = fault_name+","+str(sum_strike/2)+","+str(sum_strike)+","+str(sum_strike/4.0)+"\n"
                    fd.write(ostr)

                    dlsx = firstx - lastx
                    dlsy = firsty - lasty
                    if dlsx == 0.0 or dlsy == 0.0:
                        continue

                    lsx = dlsx / sqrt((dlsx * dlsx) + (dlsy * dlsy))
                    lsy = dlsy / sqrt((dlsx * dlsx) + (dlsy * dlsy))
                    # normal to line segment
                    azimuth = degrees(atan2(lsy, -lsx)) % 180
                    # should be mid-fault not mid fault segemnt but probs doesnt matter
                    locations = [
                        (
                            flt_ls.coords[int((len(afs) - 1) / 2)][0],
                            flt_ls.coords[int((len(afs) - 1) / 2)][1],
                        )
                    ]
                    height = m2l_utils.value_from_dtm_dtb(
                        dtm,
                        map_data.dtb,
                        map_data.dtb_null,
                        workflow["cover_map"],
                        locations,
                    )
                    ostr = "{},{},{},{},{},{},{},\n".format(
                        flt_ls.coords[int((len(flt_ls.coords) - 1) / 2)][0],
                        flt_ls.coords[int((len(flt_ls.coords) - 1) / 2)][1],
                        height,
                        azimuth,
                        fault_dip,
                        1,
                        fault_name,
                    )
                    # ostr = str(flt_ls.coords[int((len(flt_ls.coords)-1)/2)][0])+","+str(flt_ls.coords[int((len(flt_ls.coords)-1)/2)][1])+","+height+","+str(azimuth)+","+str(fault_dip)+",1,"+fault_name+"\n"
                    fo.write(ostr)

                    for pline in flt.geometry:
                        # display(pline)
                        # display(flt)
                        flt_ls = LineString(pline)
                        dlsx = (
                            flt_ls.coords[0][0]
                            - flt_ls.coords[len(flt_ls.coords) - 1][0]
                        )
                        dlsy = (
                            flt_ls.coords[0][1]
                            - flt_ls.coords[len(flt_ls.coords) - 1][1]
                        )
                        if dlsx == 0.0 or dlsy == 0.0:
                            continue

                        if sum_strike > config.run_flags["min_fault_length"]:
                            i = 0
                            saved = 0
                            for afs in flt_ls.coords:
                                # decimate to reduce number of points, but also take mid and end points of a series to keep some shape
                                if (
                                    i % config.run_flags["fault_decimate"] == 0
                                    or i == int((len(flt_ls.coords) - 1) / 2)
                                    or i == len(flt_ls.coords) - 1
                                ):
                                    if saved == 0:
                                        p1x = afs[0]
                                        p1y = afs[1]
                                    elif saved == 1:
                                        p2x = afs[0]
                                        p2y = afs[1]
                                    elif saved == 2:
                                        p3x = afs[0]
                                        p3y = afs[1]
                                        # avoids narrow angles in fault traces which geomodeller refuses to solve
                                        # should really split fault in two at apex, but life is too short
                                        if (
                                            m2l_utils.tri_angle(
                                                p2x, p2y, p1x, p1y, p3x, p3y
                                            )
                                            < 45.0
                                        ):
                                            break
                                    elif saved > 2:
                                        p1x = p2x
                                        p1y = p2y
                                        p2x = p3x
                                        p2y = p3y
                                        p3x = afs[0]
                                        p3y = afs[1]
                                        # avoids narrow angles in fault traces which geomodeller refuses to solve
                                        # should really split fault in two at apex, but life is too short
                                        if (
                                            m2l_utils.tri_angle(
                                                p2x, p2y, p1x, p1y, p3x, p3y
                                            )
                                            < 45.0
                                        ):
                                            break
                                    saved = saved + 1
                                    locations = [(afs[0], afs[1])]
                                    height = m2l_utils.value_from_dtm_dtb(
                                        dtm,
                                        map_data.dtb,
                                        map_data.dtb_null,
                                        workflow["cover_map"],
                                        locations,
                                    )
                                    # slightly randomise first and last points to avoid awkward quadruple junctions etc.
                                    # if(i == 0 or i == len(flt_ls.coords)-1):
                                    #    ostr = str(afs[0]+np.random.ranf())+","+str(afs[1]+np.random.ranf())+","+str(height)+","+fault_name+"\n"
                                    # else:
                                    ostr = "{},{},{},{}\n".format(
                                        afs[0], afs[1], height, fault_name
                                    )
                                    # ostr = str(afs[0])+","+str(afs[1])+","+str(height)+","+fault_name+"\n"
                                    f.write(ostr)
                                i = i + 1

    f.close()
    fo.close()
    fd.close()
    if config.verbose_level != VerboseLevel.NONE:
        print(
            "fault orientations saved as",
            os.path.join(config.output_path, "fault_orientations.csv"),
        )
        print(
            "fault positions saved as", os.path.join(config.output_path, "faults.csv")
        )
        print(
            "fault dimensions saved as",
            os.path.join(config.output_path, "fault_dimensions.csv"),
        )
    random.seed()


########################################
# Save fold axial traces
#
# save_fold_axial_traces(path_faults,path_fault_orientations,dtm,c_l,fault_decimate)
# Args:
# path_folds path to clipped fault layer
# path_fold_orientations directory for outputs
# dtm rasterio format elevation grid
# c_l dictionary of codes and labels specific to input geo information layers
# fold_decimate decimation factor for saving every nth input point on fold axial trace polylines
#
# Saves out csv file of fold axial trace locations after decimation.
#########################################


@beartype.beartype
def save_fold_axial_traces(config: Config, map_data: MapData, workflow: dict):
    folds_clip = map_data.get_map_data(Datatype.FOLD).copy()
    dtm = map_data.get_map_data(Datatype.DTM).open()
    # folds_clip = gpd.read_file(path_folds)
    fo = open(os.path.join(config.output_path, "fold_axial_traces.csv"), "w")
    fo.write("X,Y,Z,code,type\n")
    folds_clip = folds_clip.dropna(subset=["geometry"])

    for indx, fold in folds_clip.iterrows():
        fold_name = str(fold["GEOMETRY_OBJECT_ID"])
        if not str(fold.geometry.type) == "None":
            if fold.geometry.type == "MultiLineString":
                for mls in fold.geometry:
                    fold_ls = LineString(mls)

                    i = 0
                    for afs in fold_ls.coords:
                        if config.c_l["fold"].lower() in fold["FEATURE"].lower():
                            # decimate to reduce number of points, but also take mid and end points of a series to keep some shape
                            if (
                                i % config.run_flags["fold_decimate"] == 0
                                or i == int((len(fold_ls.coords) - 1) / 2)
                                or i == len(fold_ls.coords) - 1
                            ):
                                locations = [(afs[0], afs[1])]
                                height = m2l_utils.value_from_dtm_dtb(
                                    dtm,
                                    map_data.dtb,
                                    map_data.dtb_null,
                                    workflow["cover_map"],
                                    locations,
                                )
                                ostr = "{},{},{},FA_{},{}\n".format(
                                    afs[0],
                                    afs[1],
                                    height,
                                    fold_name,
                                    fold["TYPE"].replace(",", ""),
                                )
                                # ostr = str(afs[0])+','+str(afs[1])+','+str(height)+','+'FA_'+fold_name+','+fold['TYPE'].replace(',','')+'\n'
                                fo.write(ostr)
                        i = i + 1
            else:
                fold_ls = LineString(fold.geometry)

                i = 0
                for afs in fold_ls.coords:
                    if config.c_l["fold"].lower() in fold["FEATURE"].lower():
                        # decimate to reduce number of points, but also take mid and end points of a series to keep some shape
                        if (
                            i % config.run_flags["fold_decimate"] == 0
                            or i == int((len(fold_ls.coords) - 1) / 2)
                            or i == len(fold_ls.coords) - 1
                        ):
                            locations = [(afs[0], afs[1])]
                            height = m2l_utils.value_from_dtm_dtb(
                                dtm,
                                map_data.dtb,
                                map_data.dtb_null,
                                workflow["cover_map"],
                                locations,
                            )
                            ostr = "{},{},{},FA_{},{}\n".format(
                                afs[0],
                                afs[1],
                                height,
                                fold_name,
                                fold["TYPE"].replace(",", ""),
                            )
                            # ostr = str(afs[0])+','+str(afs[1])+','+str(height)+','+'FA_'+fold_name+','+fold['TYPE'].replace(',','')+'\n'
                            fo.write(ostr)
                    i = i + 1

    fo.close()
    print(
        "fold axial traces saved as",
        os.path.join(config.output_path, "fold_axial_traces.csv"),
    )


#########################################
# Create basal contact points with orientation from orientations and basal points
#
# Args:
# contacts geopandas object containing basal contacts
# structures geopandas object containing bedding orientations
# output_path directory for outputs
# dtm rasterio format elevation grid
# dist_buffer
# c_l dictionary of codes and labels specific to input geo information layers
#########################################


def create_basal_contact_orientations(
    contacts, structures, output_path, dtm, dtb, dtb_null, cover_map, dist_buffer, c_l
):
    f = open(os.path.join(output_path, "projected_dip_contacts2.csv"), "w")
    f.write("X,Y,Z,azimuth,dip,polarity,formation\n")
    # print("len = ",len(contacts))
    i = 0
    for indx, acontact in contacts.iterrows():  # loop through distinct linestrings
        # display(acontact[1].geometry)
        thegroup = acontact["GROUP"].replace("_", " ")
        # print("thegroup = ",thegroup)
        # subset orientations to just those with this group
        is_gp = structures["GROUP"] == thegroup
        all_structures = structures[is_gp]

        for ind, astr in all_structures.iterrows():  # loop through valid orientations
            orig = Point(astr["geometry"])
            np = acontact.geometry.interpolate(acontact.geometry.project(orig))
            if np.distance(orig) < dist_buffer:
                for line in acontact.geometry:  # loop through line segments
                    # loop through line segments
                    for pair in m2l_utils.pairs(list(line.coords)):
                        segpair = LineString((pair[0], pair[1]))
                        # line segment closest to close point
                        if segpair.distance(np) < 0.0001:
                            ddx = sin(radians(astr["DIP"]))
                            ddy = cos(radians(astr["DIP"]))
                            dlsx = pair[0][0] - pair[1][0]
                            dlsy = pair[0][1] - pair[1][1]
                            lsx = dlsx / sqrt((dlsx * dlsx) + (dlsy * dlsy))
                            lsy = dlsy / sqrt((dlsx * dlsx) + (dlsy * dlsy))
                            angle = degrees(acos((ddx * lsx) + (ddy * lsy)))

                            # dip_dir normal and contact are close enough to parallel
                            if fabs(angle - 90) < 30.0:
                                locations = [(np.x, np.y)]
                                height = m2l_utils.value_from_dtm_dtb(
                                    dtm, dtb, dtb_null, cover_map, locations
                                )
                                # normal to line segment
                                ls_ddir = degrees(atan2(lsy, -lsx))

                                if (ddx * lsy) + (
                                    -ddy * lsx
                                ) < 0:  # dot product tests right quadrant
                                    ls_ddir = (ls_ddir - 180) % 360
                                ostr = "{},{},{},{},{},{},{}\n".format(
                                    np.x,
                                    np.y,
                                    height,
                                    ls_ddir,
                                    astr["DIP"],
                                    1,
                                    acontact["UNIT_NAME"]
                                    .replace(" ", "_")
                                    .replace("-", "_"),
                                )
                                # ostr = str(np.x)+","+str(np.y)+","+height+","+str(ls_ddir)+","+str(astr["DIP"])+",1,"+acontact["UNIT_NAME"].replace(" ","_").replace("-","_")+"\n"
                                f.write(ostr)
                                i = i + 1

    f.close()
    print(
        "basal contact orientations saved as",
        os.path.join(output_path, "projected_dip_contacts2.csv"),
    )


#########################################
# For each pluton polygon, create dip info based on ideal form with azimuth parallel to local contact
#
# process_plutons(tmp_path,output_path,geol_clip,local_paths,dtm,pluton_form,pluton_dip,contact_decimate,c_l)
# Args:
# tmp_path directory of temporary outputs from m2l
# output_path directory of outputs from m2lc geol_clip path ot clipped geology layer local_paths Boolean to control if
# local on web data is used dtm rasterio format elevation grid
# pluton_form fundamental pluton geometry (one of domes, saucers, pendant, batholith) pluton_dip fix dip for all pluton
# contacts contact_decimate decimation factor for saving every nth input point on contact polylines
# c_l dictionary of codes and labels specific to input geo information layers
#
# Saves out csv of locations of intrusive contacts and csv of contact orientations. Orientations can take one of four modes
# (inward/ outward dipping normal/reverse polarity) and have dip direction normal to local contact and fixed arbitrary dip
# For each instruve but not sill polygon, find older neighbours and store decimated contact points. Also store dipping contact
# orientations (user defined, just because) with four possible sub-surface configurations:
# saucers: +++/ batholiths: +++/_ __ _+++ domes: /‾+++‾ pendants: +++\ _/+++
#
# Saves out orientations and contact points
#########################################


@beartype.beartype
def process_plutons(config: Config, map_data, workflow: dict):
    if config.verbose_level != VerboseLevel.NONE:
        print("processing plutons...")
    groups = np.genfromtxt(
        os.path.join(config.tmp_path, "groups.csv"), delimiter=",", dtype="U100"
    )

    if len(groups.shape) == 1:
        ngroups = len(groups) - 1
        orig_ngroups = ngroups

        gp_ages = np.zeros((1000, 3))
        gp_names = np.zeros((1000), dtype="U100")

        for i in range(0, ngroups):
            gp_ages[i, 0] = -1e6  # group max_age
            gp_ages[i, 1] = 1e6  # group min_age
            gp_ages[i, 2] = i  # group index
            gp_names[i] = groups[i + 1].replace("\n", "")
    else:
        ngroups = len(groups[0]) - 1
        orig_ngroups = ngroups

        gp_ages = np.zeros((1000, 3))
        gp_names = np.zeros((1000), dtype="U100")

        for i in range(0, ngroups):
            gp_ages[i, 0] = -1e6  # group max_age
            gp_ages[i, 1] = 1e6  # group min_age
            gp_ages[i, 2] = i  # group index
            gp_names[i] = groups[0][i + 1].replace("\n", "")

    allc = open(os.path.join(config.output_path, "all_ign_contacts.csv"), "w")
    allc.write("GROUP_,id,x,y,z,code\n")
    ac = open(os.path.join(config.output_path, "ign_contacts.csv"), "w")
    ac.write("X,Y,Z,formation\n")
    ao = open(
        os.path.join(
            config.output_path,
            "ign_orientations_" + config.run_flags["pluton_form"] + ".csv",
        ),
        "w",
    )
    ao.write("X,Y,Z,azimuth,dip,polarity,formation\n")

    j = 0
    allpts = 0
    ls_dict = {}
    ls_dict_decimate = {}
    id = 0
    dtm = map_data.get_map_data(Datatype.DTM).open()
    geology = map_data.get_map_data(Datatype.GEOLOGY)
    geol_clip = geology[geology.area > config.run_flags["min_pluton_area"]]
    for indx, ageol in geol_clip.iterrows():
        ades = str(ageol["DESCRIPTION"])
        arck = str(ageol["ROCKTYPE1"])
        if str(ageol["GROUP"]) == "None":
            agroup = str(ageol["UNIT_NAME"])
        else:
            agroup = str(ageol["GROUP"])

        for i in range(0, ngroups):
            if gp_names[i] == agroup:
                if int(ageol["MAX_AGE"]) > gp_ages[i][0]:
                    gp_ages[i][0] = ageol["MAX_AGE"]
                if int(ageol["MIN_AGE"]) < gp_ages[i][1]:
                    gp_ages[i][1] = ageol["MIN_AGE"]
        if config.c_l["intrusive"] in arck and config.c_l["sill"] not in ades:
            newgp = str(ageol["UNIT_NAME"])
            if str(ageol["GROUP"]) == "None":
                agp = str(ageol["UNIT_NAME"])
            else:
                agp = str(ageol["GROUP"])

            if newgp not in gp_names:
                gp_names[ngroups] = newgp
                gp_ages[ngroups][0] = ageol["MAX_AGE"]
                gp_ages[ngroups][1] = ageol["MIN_AGE"]
                gp_ages[ngroups][2] = ngroups
                ngroups = ngroups + 1

            for inset in np.arange(-5000, 10001, 1000):
                pluton_buffer = ageol.geometry.buffer(inset)

                if pluton_buffer.area > 0:
                    locations = [(pluton_buffer.centroid.x, pluton_buffer.centroid.y)]
                    height = m2l_utils.value_from_dtm_dtb(
                        dtm,
                        map_data.dtb,
                        map_data.dtb_null,
                        workflow["cover_map"],
                        locations,
                    )
                    plu_dense = densify(pluton_buffer, 1000)
                    if plu_dense.geom_type == "MultiPolygon":
                        for apoly in plu_dense:
                            for x, y in apoly.exterior.coords:
                                if config.run_flags["pluton_form"] == "saucers":
                                    depth = (
                                        float(height)
                                        - 2000
                                        + (0.00002 * (inset + 10000) ** 2)
                                    )
                                else:
                                    depth = (
                                        float(height)
                                        + 2000
                                        - (0.00002 * (inset + 10000) ** 2)
                                    )
                                ostr = "{},{},{},{}\n".format(
                                    x,
                                    y,
                                    depth,
                                    newgp.replace(" ", "_").replace("-", "_"),
                                )
                                ac.write(ostr)
                    else:
                        for x, y in plu_dense.exterior.coords:
                            if config.run_flags["pluton_form"] == "saucers":
                                depth = (
                                    float(height)
                                    + -2000
                                    + (0.00002 * (inset + 10000) ** 2)
                                )
                            else:
                                depth = (
                                    float(height)
                                    + 2000
                                    - (0.00002 * (inset + 10000) ** 2)
                                )
                            ostr = "{},{},{},{}\n".format(
                                x, y, depth, newgp.replace(" ", "_").replace("-", "_")
                            )
                            ac.write(ostr)

            neighbours = []
            j += 1
            # central_age = ageol["MIN_AGE"]  # absolute age of central polygon
            central_poly = ageol.geometry
            for ind, bgeol in geol_clip.iterrows():  # potential neighbouring polygons
                if ageol.geometry != bgeol.geometry:  # do not compare with self
                    if ageol.geometry.intersects(bgeol.geometry):  # is a neighbour
                        neighbours.append(
                            [
                                (
                                    bgeol["UNIT_NAME"],
                                    bgeol["MIN_AGE"],
                                    bgeol["ROCKTYPE1"],
                                    bgeol["DESCRIPTION"],
                                    bgeol.geometry,
                                )
                            ]
                        )
            # display(neighbours)
            if len(neighbours) > 0:
                for i in range(0, len(neighbours)):
                    if (
                        (
                            config.c_l["intrusive"] in neighbours[i][0][2]
                            and config.c_l["sill"] not in ades
                        )
                        # or ('intrusive' not in neighbours[i][0][2]) and neighbours[i][0][1] > central_age ): # neighbour is older than central
                        or (config.c_l["intrusive"] not in neighbours[i][0][2])
                        and neighbours[i][0][1]
                    ):  # neighbour is older than central
                        older_polygon = neighbours[i][0][4]
                        if not central_poly.is_valid:
                            central_poly = central_poly.buffer(0)
                        if not older_polygon.is_valid:
                            older_polygon = older_polygon.buffer(0)
                        # centroid = central_poly.centroid

                        LineStringC = central_poly.intersection(older_polygon)
                        if (
                            LineStringC.wkt.split(" ")[0] == "MULTIPOLYGON"
                            or LineStringC.wkt.split(" ")[0] == "POLYGON"
                        ):  # ignore polygon intersections for now, worry about them later!
                            if config.verbose_level != VerboseLevel.NONE:
                                print(
                                    ageol["GEOMETRY_OBJECT_ID"],
                                    "debug:",
                                    LineStringC.wkt.split(" ")[0],
                                )
                            continue

                        elif (
                            LineStringC.wkt.split(" ")[0] == "MULTILINESTRING"
                            or LineStringC.wkt.split(" ")[0] == "GEOMETRYCOLLECTION"
                        ):
                            k = 0
                            ls_dict[id] = {
                                "id": id,
                                "UNIT_NAME": newgp,
                                "GROUP": newgp,
                                "geometry": LineStringC,
                            }
                            id = id + 1
                            # first = True  # use first found dist so all arcs converge to same point
                            for lineC in LineStringC.geoms:  # process all linestrings
                                if lineC.wkt.split(" ")[0] == "LINESTRING":
                                    # decimate to reduce number of points, but also take second and third point of a series to keep gempy happy
                                    if (
                                        k % config.run_flags["contact_decimate"] == 0
                                        or k == int((len(LineStringC) - 1) / 2)
                                        or k == len(LineStringC) - 1
                                    ):
                                        dlsx = lineC.coords[0][0] - lineC.coords[1][0]
                                        dlsy = lineC.coords[0][1] - lineC.coords[1][1]
                                        lsx = dlsx / sqrt((dlsx * dlsx) + (dlsy * dlsy))
                                        lsy = dlsy / sqrt((dlsx * dlsx) + (dlsy * dlsy))

                                        locations = [
                                            (lineC.coords[0][0], lineC.coords[0][1])
                                        ]
                                        height = m2l_utils.value_from_dtm_dtb(
                                            dtm,
                                            map_data.dtb,
                                            map_data.dtb_null,
                                            workflow["cover_map"],
                                            locations,
                                        )
                                        # normal to line segment
                                        azimuth = (
                                            180 + degrees(atan2(lsy, -lsx))
                                        ) % 360
                                        # pt just a bit in/out from line
                                        testpx = lineC.coords[0][0] - lsy
                                        testpy = lineC.coords[0][0] + lsx

                                        if ageol.geometry.type == "Polygon":
                                            if Polygon(ageol.geometry).contains(
                                                Point(testpx, testpy)
                                            ):
                                                azimuth = (azimuth - 180) % 360
                                        else:
                                            if MultiPolygon(ageol.geometry).contains(
                                                Point(testpx, testpy)
                                            ):
                                                azimuth = (azimuth - 180) % 360

                                        if config.run_flags["pluton_form"] == "saucers":
                                            polarity = 1
                                            # ostr = str(lineC.coords[0][0])+","+str(lineC.coords[0][1])+","+str(height)+","+str(azimuth)+","+str(config.run_flags['pluton_dip'])+",1,"+newgp.replace(" ","_").replace("-","_")+"\n"
                                        elif config.run_flags["pluton_form"] == "domes":
                                            polarity = 0
                                            azimuth = (azimuth - 180) % 360
                                            # ostr = str(lineC.coords[0][0])+","+str(lineC.coords[0][1])+","+str(height)+","+str(azimuth)+","+str(config.run_flags['pluton_dip'])+",0,"+newgp.replace(" ","_").replace("-","_")+"\n"
                                        elif (
                                            config.run_flags["pluton_form"] == "pendant"
                                        ):
                                            polarity = 0
                                            # ostr = str(lineC.coords[0][0])+","+str(lineC.coords[0][1])+","+str(height)+","+str(azimuth)+","+str(config.run_flags['pluton_dip'])+",0,"+newgp.replace(" ","_").replace("-","_")+"\n"
                                        else:  # config.run_flags['pluton_form']  ==  batholith
                                            polarity = 1
                                            azimuth = (azimuth - 180) % 360
                                            # ostr = str(lineC.coords[0][0])+","+str(lineC.coords[0][1])+","+str(height)+","+str(azimuth)+","+str(config.run_flags['pluton_dip'])+",1,"+newgp.replace(" ","_").replace("-","_")+"\n"
                                        ostr = "{},{},{},{},{},{},{}\n".format(
                                            lineC.coords[0][0],
                                            lineC.coords[0][1],
                                            height,
                                            azimuth,
                                            config.run_flags["pluton_dip"],
                                            polarity,
                                            newgp.replace(" ", "_").replace("-", "_"),
                                        )
                                        ao.write(ostr)

                                    k += 1
                        # apparently this is not needed
                        elif LineStringC.wkt.split(" ")[0] == "LINESTRING":
                            k = 0
                            lineC = LineString(LineStringC)
                            # decimate to reduce number of points, but also take second and third point of a series to keep gempy happy
                            if (
                                k % config.run_flags["contact_decimate"] == 0
                                or k == int((len(LineStringC) - 1) / 2)
                                or k == len(LineStringC) - 1
                            ):
                                # doesn't like point right on edge?
                                locations = [(lineC.coords[0][0], lineC.coords[0][1])]
                                if (
                                    lineC.coords[0][0] > dtm.bounds[0]
                                    and lineC.coords[0][0] < dtm.bounds[2]
                                    and lineC.coords[0][1] > dtm.bounds[1]
                                    and lineC.coords[0][1] < dtm.bounds[3]
                                ):
                                    height = m2l_utils.value_from_dtm_dtb(
                                        dtm,
                                        map_data.dtb,
                                        map_data.dtb_null,
                                        workflow["cover_map"],
                                        locations,
                                    )
                                    ostr = "{},{},{},{}\n".format(
                                        lineC.coords[0][0],
                                        lineC.coords[0][1],
                                        height,
                                        newgp.replace(" ", "_").replace("-", "_"),
                                    )
                                    # ostr = str(lineC.coords[0][0])+","+str(lineC.coords[0][1])+","+height+","+newgp.replace(" ","_").replace("-","_")+"\n"
                                    ac.write(ostr)
                                    allc.write(
                                        agp
                                        + ","
                                        + str(ageol["GEOMETRY_ONJECT_ID"])
                                        + ","
                                        + ostr
                                    )
                                    ls_dict_decimate[allpts] = {
                                        "id": allpts,
                                        "UNIT_NAME": newgp,
                                        "GROUP": newgp,
                                        "geometry": Point(
                                            lineC.coords[0][0], lineC.coords[0][1]
                                        ),
                                    }
                                    allpts += 1
                                else:
                                    continue
                            else:
                                if (
                                    lineC.coords[0][0] > dtm.bounds[0]
                                    and lineC.coords[0][0] < dtm.bounds[2]
                                    and lineC.coords[0][1] > dtm.bounds[1]
                                    and lineC.coords[0][1] < dtm.bounds[3]
                                ):
                                    height = m2l_utils.value_from_dtm_dtb(
                                        dtm,
                                        map_data.dtb,
                                        map_data.dtb_null,
                                        workflow["cover_map"],
                                        locations,
                                    )
                                    ostr = "{},{},{},{}\n".format(
                                        lineC.coords[0][0],
                                        lineC.coords[0][1],
                                        height,
                                        newgp.replace(" ", "_").replace("-", "_"),
                                    )
                                    # ostr = str(lineC.coords[0][0])+","+str(lineC.coords[0][1])+","+height+","+newgp.replace(" ","_").replace("-","_")+"\n"
                                    # ls_dict_decimate[allpts]  =  {"id": id,"CODE":ageol['CODE'],"GROUP_":ageol['GROUP_'], "geometry": Point(lineC.coords[0][0],lineC.coords[0][1])}
                                    allc.write(
                                        agp + "," + str(ageol["UNIT_NAME"]) + "," + ostr
                                    )
                                    allpts += 1

                            # decimate to reduce number of points, but also take second and third point of a series to keep gempy happy
                            if (
                                k % config.run_flags["contact_decimate"] == 0
                                or k == int((len(LineStringC) - 1) / 2)
                                or k == len(LineStringC) - 1
                            ):
                                dlsx = lineC.coords[0][0] - lineC.coords[1][0]
                                dlsy = lineC.coords[0][1] - lineC.coords[1][1]
                                lsx = dlsx / sqrt((dlsx * dlsx) + (dlsy * dlsy))
                                lsy = dlsy / sqrt((dlsx * dlsx) + (dlsy * dlsy))

                                locations = [(lineC.coords[0][0], lineC.coords[0][1])]
                                height = m2l_utils.value_from_dtm_dtb(
                                    dtm,
                                    map_data.dtb,
                                    map_data.dtb_null,
                                    workflow["cover_map"],
                                    locations,
                                )
                                # normal to line segment
                                azimuth = (180 + degrees(atan2(lsy, -lsx))) % 360
                                # pt just a bit in/out from line
                                testpx = lineC.coords[0][0] - lsy
                                testpy = lineC.coords[0][0] + lsx

                                if ageol.geometry.type == "Polygon":
                                    if Polygon(ageol.geometry).contains(
                                        Point(testpx, testpy)
                                    ):
                                        azimuth = (azimuth - 180) % 360
                                else:
                                    if MultiPolygon(ageol.geometry).contains(
                                        Point(testpx, testpy)
                                    ):
                                        azimuth = (azimuth - 180) % 360

                                if config.run_flags["pluton_form"] == "saucers":
                                    polarity = 1
                                    # ostr = str(lineC.coords[0][0])+","+str(lineC.coords[0][1])+","+str(height)+","+str(azimuth)+","+str(config.run_flags['pluton_dip'])+",1,"+newgp.replace(" ","_").replace("-","_")+"\n"
                                elif config.run_flags["pluton_form"] == "domes":
                                    polarity = 0
                                    azimuth = (azimuth - 180) % 360
                                    # ostr = str(lineC.coords[0][0])+","+str(lineC.coords[0][1])+","+str(height)+","+str(azimuth)+","+str(config.run_flags['pluton_dip'])+",0,"+newgp.replace(" ","_").replace("-","_")+"\n"
                                elif config.run_flags["pluton_form"] == "pendant":
                                    polarity = 0
                                    # ostr = str(lineC.coords[0][0])+","+str(lineC.coords[0][1])+","+str(height)+","+str(azimuth)+","+str(config.run_flags['pluton_dip'])+",0,"+newgp.replace(" ","_").replace("-","_")+"\n"
                                else:  # config.run_flags['pluton_form']  ==  batholith
                                    polarity = 1
                                    azimuth = (azimuth - 180) % 360
                                    # ostr = str(lineC.coords[0][0])+","+str(lineC.coords[0][1])+","+str(height)+","+str(azimuth)+","+str(config.run_flags['pluton_dip'])+",1,"+newgp.replace(" ","_").replace("-","_")+"\n"
                                ostr = "{},{},{},{},{},{},{}\n".format(
                                    lineC.coords[0][0],
                                    lineC.coords[0][1],
                                    height,
                                    azimuth,
                                    config.run_flags["pluton_dip"],
                                    polarity,
                                    newgp.replace(" ", "_")
                                    .replace("-", "_")
                                    .replace(",", "_"),
                                )
                                ao.write(ostr)
                            k += 1
                        # apparently this is not needed
                        elif LineStringC.wkt.split(" ")[0] == "POINT":
                            k = 0
                            k += 1
                        else:
                            k = 0
                            k += 1
    ac.close()
    ao.close()
    allc.close()

    an = open(os.path.join(config.tmp_path, "groups2.csv"), "w")

    for i in range(0, orig_ngroups):
        if config.verbose_level != VerboseLevel.NONE:
            print(i, gp_names[i].replace(" ", "_").replace("-", "_"))
        an.write(gp_names[i].replace(" ", "_").replace("-", "_") + "\n")
    an.close()

    all_sorts = pd.read_csv(os.path.join(config.tmp_path, "all_sorts.csv"), sep=",")

    as_2 = open(os.path.join(config.tmp_path, "all_sorts.csv"), "r")
    contents = as_2.readlines()
    as_2.close

    all_sorts_file = open(os.path.join(config.tmp_path, "all_sorts2.csv"), "w")
    all_sorts_file.write(
        "index,group number,index in group,number in group,code,group\n"
    )
    j = 1
    if workflow["cover_map"]:
        all_sorts_file.write("-2,0,1,2,cover_up,cover\n")
        all_sorts_file.write("-1,0,2,2,cover,cover\n")

    for i in range(1, len(all_sorts) + 1):
        # don't write out if already there in new groups list#
        all_sorts_file.write(contents[i])

    all_sorts_file.close()
    if config.verbose_level != VerboseLevel.NONE:
        print("pluton contacts and orientations saved as:")
        print(os.path.join(config.output_path, "ign_contacts.csv"))
        print(
            os.path.join(
                config.output_path,
                "ign_orientations_" + config.run_flags["pluton_form"] + ".csv",
            )
        )


###################################
# Remove orientations that don't belong to actual formations in model
#
# tidy_data(output_path,tmp_path,use_gcode,use_interpolations,pluton_form)
# Args:
# output_path directory of outputs from m2lc
# tmp_path directory of temporary outputs from m2l use_gcode list of groups that will be retained if possible
# use_interpolations include extra data from dip/contact interpolation pluton_form fundamental
# pluton geometry (one of domes, saucers, pendant, batholith)
#
# Removes formations that don’t belong to a group, groups with no formations, orientations
# without formations, contacts without formations etc so gempy and other packages don’t have a fit.
###################################


@beartype.beartype
def tidy_data(config: Config, map_data: MapData, use_group, inputs):
    use_projected_contacts = True

    contacts = pd.read_csv(os.path.join(config.output_path, "contacts4.csv"), sep=",")
    contacts["source"] = "strat"
    all_orientations = pd.read_csv(
        os.path.join(config.output_path, "orientations.csv"), sep=","
    )
    all_orientations["source"] = "observed"
    intrusive_contacts = pd.read_csv(
        os.path.join(config.output_path, "ign_contacts.csv"), sep=","
    )
    intrusive_contacts["source"] = "intrusive"
    all_sorts = pd.read_csv(os.path.join(config.tmp_path, "all_sorts2.csv"), sep=",")

    if "invented_orientations" in inputs and os.path.exists(
        os.path.join(config.output_path, "empty_series_orientations.csv")
    ):
        invented_orientations = pd.read_csv(
            os.path.join(config.output_path, "empty_series_orientations.csv"), sep=","
        )
        invented_orientations["source"] = "invented"
        all_orientations = pd.concat(
            [all_orientations, invented_orientations], sort=False
        )
    elif "invented_orientations" in inputs and not os.path.exists(
        os.path.join(config.output_path, "empty_series_orientations.csv")
    ):
        if config.verbose_level != VerboseLevel.NONE:
            print("No invented orientations available for merging.")

    if "interpolated_orientations" in inputs and os.path.exists(
        os.path.join(config.tmp_path, "combo_full.csv")
    ):
        interpolated_orientations = pd.read_csv(
            os.path.join(config.tmp_path, "combo_full.csv"), sep=","
        )
        interpolated_orientations["source"] = "interpolated"
        all_orientations = pd.concat(
            [all_orientations, interpolated_orientations.iloc[::2, :]], sort=False
        )
    elif "interpolated_orientations" in inputs and not os.path.exists(
        os.path.join(config.tmp_path, "combo_full.csv")
    ):
        if config.verbose_level != VerboseLevel.NONE:
            print("No interpolated orientations available for merging.")

    if "intrusive_orientations" in inputs and os.path.exists(
        os.path.join(
            config.output_path,
            "ign_orientations_" + config.run_flags["pluton_form"] + ".csv",
        )
    ):
        intrusive_orientations = pd.read_csv(
            os.path.join(
                config.output_path,
                "ign_orientations_" + config.run_flags["pluton_form"] + ".csv",
            ),
            sep=",",
        )
        intrusive_orientations["source"] = "intrusive"
        all_orientations = pd.concat(
            [all_orientations, intrusive_orientations], sort=False
        )
        if config.verbose_level != VerboseLevel.NONE:
            print(len(intrusive_orientations), " intrusive orientations merged.")
    elif "intrusive_orientations" in inputs and not os.path.exists(
        os.path.join(
            config.output_path,
            "ign_orientations_" + config.run_flags["pluton_form"] + ".csv",
        )
    ):
        if config.verbose_level != VerboseLevel.NONE:
            print("No intrusive orientations available for merging.")

    if "fat_orientations" in inputs and os.path.exists(
        os.path.join(config.output_path, "fold_axial_trace_orientations2.csv")
    ):
        fat_orientations = pd.read_csv(
            os.path.join(config.output_path, "fold_axial_trace_orientations2.csv"),
            sep=",",
        )
        fat_orientations["source"] = "fold_axial_trace"
        all_orientations = pd.concat([all_orientations, fat_orientations], sort=False)
    elif "fat_orientations" in inputs and not os.path.exists(
        os.path.join(config.output_path, "fold_axial_trace_orientations2.csv")
    ):
        if config.verbose_level != VerboseLevel.NONE:
            print("No fat orientations available for merging.")

    if "near_fault_orientations" in inputs and os.path.exists(
        os.path.join(config.tmp_path, "ex_f_combo_full.csv")
    ):
        near_fault_orientations = pd.read_csv(
            os.path.join(config.tmp_path, "ex_f_combo_full.csv"), sep=","
        )
        near_fault_orientations["source"] = "near_fault"
        all_orientations = pd.concat(
            [all_orientations, near_fault_orientations], sort=False
        )
    elif "near_fault_orientations" in inputs and not os.path.exists(
        os.path.join(config.tmp_path, "ex_f_combo_full.csv")
    ):
        if config.verbose_level != VerboseLevel.NONE:
            print("No near fault orientations available for merging.")

    if "cover_orientations" in inputs and os.path.exists(
        os.path.join(config.output_path, "cover_orientations.csv")
    ):
        cover_orientations = pd.read_csv(
            os.path.join(config.output_path, "cover_orientations.csv"), sep=","
        )
        cover_orientations["source"] = "cover"
        all_orientations = pd.concat([all_orientations, cover_orientations], sort=False)
    elif "cover_orientations" in inputs and not os.path.exists(
        os.path.join(config.output_path, "cover_orientations.csv")
    ):
        if config.verbose_level != VerboseLevel.NONE:
            print("No cover orientations available for merging.")

    if "contact_orientations" in inputs and os.path.exists(
        os.path.join(config.output_path, "contact_orientations.csv")
    ):
        contact_orientations = pd.read_csv(
            os.path.join(config.output_path, "contact_orientations.csv"), sep=","
        )
        contact_orientations["source"] = "contact_orientations"
        all_orientations = pd.concat(
            [all_orientations, contact_orientations], sort=False
        )
    elif "contact_orientations" in inputs and not os.path.exists(
        os.path.join(config.output_path, "contact_orientations.csv")
    ):
        if config.verbose_level != VerboseLevel.NONE:
            print("No contact orientations available for merging.")

    # display(cover_orientations)
    # display(all_orientations)
    all_orientations.reset_index(inplace=True)
    unique_allsorts_contacts = set(all_sorts["code"])

    # all_sorts.set_index('code',  inplace=True)

    all_contacts = pd.concat([intrusive_contacts, contacts], sort=False)
    if use_projected_contacts and os.path.exists(
        os.path.join(config.output_path, "contact_projections.csv")
    ):
        projected_contacts = pd.read_csv(
            os.path.join(config.output_path, "contact_projections.csv"), sep=","
        )
        all_contacts = pd.concat([all_contacts, projected_contacts], sort=False)

    if "cover_contacts" in inputs and os.path.exists(
        os.path.join(config.output_path, "cover_grid.csv")
    ):
        cover_contacts = pd.read_csv(
            os.path.join(config.output_path, "cover_grid.csv"), sep=","
        )
        cover_contacts["source"] = "cover_contact"
        all_contacts = pd.concat([all_contacts, cover_contacts], sort=False)
    elif "cover_contacts" in inputs and not os.path.exists(
        os.path.join(config.output_path, "cover_grid.csv")
    ):
        if config.verbose_level != VerboseLevel.NONE:
            print("No cover grid contacts available for merging.")

    if "fault_tip_contacts" in inputs:
        fault_tip_contacts = pd.read_csv(
            os.path.join(config.output_path, "fault_tip_contacts.csv"), sep=","
        )
        fault_tip_contacts["source"] = "fault_tip_contacts"
        all_contacts = pd.concat([all_contacts, fault_tip_contacts], sort=False)
    elif "fault_tip_contacts" in inputs and not os.path.exists(
        os.path.join(config.output_path, "fault_tip_contacts.csv")
    ):
        if config.verbose_level != VerboseLevel.NONE:
            print("No fault tip contacts available for merging.")

    all_groups = set(all_sorts["group"])
    all_contacts.reset_index(inplace=True)
    all_contacts.to_csv(
        os.path.join(config.output_path, "contacts_clean.csv"), index=None, header=True
    )

    unique_contacts = set(all_contacts["formation"])
    # Remove groups that don't have any contact info
    if config.verbose_level != VerboseLevel.NONE:
        print("--------------------------")
        print("all_groups")
        print(all_groups)
        print("unique_contacts")
        print(unique_contacts)
        print("unique_allsorts_contacts")
        print(unique_allsorts_contacts)
        print("--------------------------")
    no_contacts = []
    groups = []
    for agroup in all_groups:
        found = False
        for acontact in all_contacts.iterrows():
            if acontact[1]["formation"] in unique_allsorts_contacts:
                df = all_sorts[all_sorts["code"] == acontact[1]["formation"]]
                if len(df) > 0 and df.iloc[0]["group"] in agroup:
                    found = True
                    break
        if not found:
            no_contacts.append(agroup)
            if config.verbose_level != VerboseLevel.NONE:
                print("no contacts for the group:", agroup)
        else:
            groups.append(agroup)
    # print(groups)
    # print(no_contacts)

    # Update list of all groups that have formations info

    f = open(os.path.join(config.tmp_path, "groups2.csv"), "r")
    contents = f.readlines()
    f.close

    # ngroups = contents[0].split(" ")
    # ngroups = int(ngroups[1])
    ngroups = len(contents)
    no_contacts = []
    groups = []

    for i in range(0, ngroups):
        # print(i,ngroups,contents[i])
        found = False
        # print('GROUP',agroup)
        for acontact in all_contacts.iterrows():
            if acontact[1]["formation"] in unique_allsorts_contacts:
                df = all_sorts[all_sorts["code"] == acontact[1]["formation"]]
                if (
                    len(df) > 0
                    and df.iloc[0]["group"] in contents[i]
                    and df.iloc[0]["group"] in use_group
                ):
                    # if(all_sorts.loc[acontact[1]['formation']]['group'] in contents[i] and all_sorts.loc[acontact[1]['formation']]['group'] in use_group):
                    found = True
                    break
        if not found:
            no_contacts.append(contents[i].replace("\n", ""))
            # print('no contacts for the group:',contents[i].replace("\n",""))
        else:
            groups.append(contents[i].replace("\n", ""))

    # Make new list of groups
    # print('groups contents',len(groups),len(contents))
    fgp = open(os.path.join(config.tmp_path, "groups_clean.csv"), "w")
    for i in range(0, len(groups)):
        fgp.write(groups[i].replace("\n", "") + "\n")
    fgp.close()

    # print(all_groups,use_group)
    if False:
        # Remove orientations with no equivalent formations info
        for agroup in all_groups:
            found = False
            for ano in all_orientations.iterrows():
                # print(ano[1]['formation'])
                # print(all_sorts.loc[ano[1]['formation']]['group'])
                if ano[1]["formation"] in unique_allsorts_contacts:
                    if (
                        all_sorts.loc[ano[1]["formation"]]["group"] in agroup
                        and all_sorts.loc[ano[1]["formation"]]["group"] in use_group
                    ):
                        found = True
                        break
            if not found:
                no_contacts.append(agroup)
                print("no orientations for the group:", agroup)

    # print(no_contacts)

    # Update master list of  groups and formations info

    fas = open(os.path.join(config.tmp_path, "all_sorts_clean.csv"), "w")
    fas.write(
        "index,group number,index in group,number in group,code,group,supergroup,uctype\n"
    )

    sgf = open(os.path.join(config.tmp_path, "super_groups.csv"))
    lines = sgf.readlines()
    sgf.close()
    index = 0
    for a_sort in all_sorts.iterrows():
        if a_sort[1]["group"] not in no_contacts:
            for sg in range(len(lines)):
                for line in lines[sg].split(","):
                    if a_sort[1]["group"] == line:
                        supergroup = "supergroup_" + str(sg)
            ostr = "{},{},{},{},{},{},{},{}\n".format(
                index,
                a_sort[1]["group number"],
                a_sort[1]["index in group"],
                a_sort[1]["number in group"],
                a_sort[1]["code"],
                a_sort[1]["group"],
                supergroup,
                "erode",
            )
            # ostr = str(a_sort[1]['index'])+","+str(a_sort[1]['group number'])+","+str(a_sort[1]['index in group'])+","+str(a_sort[1]['number in group'])+","+a_sort[0]+","+a_sort[1]['group']+",erode\n"
            fas.write(ostr)
            index = index + 1
    fas.close()

    # add extra column for stratigraphy to specify intrsuve or strata (sed or volc)
    all_sorts = pd.read_csv(
        os.path.join(config.tmp_path, "all_sorts_clean.csv"), sep=","
    )

    intrusive_contacts = pd.read_csv(
        os.path.join(config.output_path, "ign_contacts.csv"), sep=","
    )

    geol = map_data.get_map_data(Datatype.GEOLOGY).copy()
    geol = geol.drop_duplicates(subset="UNIT_NAME", keep="first")
    geol["UNIT_NAME"] = geol["UNIT_NAME"].replace("-", "_")
    # geol=geol.set_index('code')
    slist = []
    for ind, unit in all_sorts.iterrows():
        df = geol[geol["UNIT_NAME"] == unit["code"]]
        if unit["code"] == "cover" or unit["code"] == "cover_up":
            slist.append("cover")
        elif (
            len(df) > 0
            and config.c_l["intrusive"] in df["ROCKTYPE1"]
            and config.c_l["sill"] not in df["DESCRIPTION"]
        ):
            slist.append("intrusion")
        else:
            slist.append("sediment")

    all_sorts.insert(6, "strat_type", slist, True)
    all_sorts.to_csv(os.path.join(config.tmp_path, "all_sorts_clean.csv"), index=False)
    # all_sorts = all_sorts.set_index('code')
    # Update orientation info

    fao = open(os.path.join(config.output_path, "orientations_clean.csv"), "w")
    fao.write("X,Y,Z,azimuth,dip,polarity,formation,source\n")
    all_sort_codes = set(all_sorts["code"])
    # print("#############################################")
    # print(no_contacts,unique_contacts,all_sorts,all_sort_codes,use_group)
    # print("#############################################")

    for ind, ano in all_orientations.iterrows():
        if ano["formation"] in all_sort_codes:
            # fix here################################
            df = all_sorts[all_sorts["code"] == ano["formation"]]
            if (
                len(df) == 0
                or df.iloc[0]["group"] in no_contacts
                or not ano["formation"] in unique_contacts
                or not df.iloc[0]["group"] in use_group
            ):
                continue
                # print('dud orientation:',ano[1]['formation'])
            else:
                ostr = "{},{},{},{},{},{},{},{}\n".format(
                    ano["X"],
                    ano["Y"],
                    ano["Z"],
                    ano["azimuth"],
                    ano["dip"],
                    ano["polarity"],
                    ano["formation"],
                    ano["source"],
                )
                # ostr = str(ano['X'])+","+str(ano['Y'])+","+str(ano['Z'])+","+\
                #     str(ano['azimuth'])+","+str(ano['dip'])+","+str(ano['polarity'])+","+ano['formation']+"\n"
                fao.write(ostr)

    fao.close()

    # Update formation info
    # age_sorted = pd.read_csv(
    #     os.path.join(config.tmp_path, "age_sorted_groups.csv"), sep=","
    # )

    # newdx = 1
    # gpdx = 1
    # fas = open(os.path.join(config.tmp_path,'all_sorts_clean.csv'),"w")
    # fas.write('index,group number,index in group,number in group,code,group,uctype\n')
    # if(workflow['cover_map']):
    # fas.write('-1,0,1,1,cover,cover,erode\n')
    # for a_sort in age_sorted.iterrows():
    # if(a_sort[1]['group_'] not in no_contacts):
    # for old_sort in all_sorts.iterrows():
    # if(a_sort[1]['group_'] ==  old_sort[1]['group']):
    # ostr = "{},{},{},{},{},{},{}\n"\
    # .format(newdx,gpdx,old_sort[1]['index in group'],old_sort[1]['number in group'],old_sort[0],old_sort[1]['group'],'erode')
    # #ostr = str(newdx)+","+str(gpdx)+","+str(old_sort[1]['index in group'])+","+str(old_sort[1]['number in group'])+","+old_sort[0]+","+old_sort[1]['group']+",erode\n"
    # fas.write(ostr)
    # newdx = newdx+1
    # gpdx = gpdx+1
    # fas.close()

    # add missing formation thickness estimates
    sum_thick = pd.read_csv(
        os.path.join(config.output_path, "formation_summary_thicknesses.csv")
    )
    all_sorts = pd.read_csv(os.path.join(config.tmp_path, "all_sorts_clean.csv"))
    found_codes = sum_thick["formation"].unique()
    median_th = sum_thick["thickness median"].median()
    fs = open(
        os.path.join(config.output_path, "formation_summary_thicknesses.csv"), "a+"
    )

    for ind, a_s in all_sorts.iterrows():
        if a_s["code"] == "cover" or a_s["code"] == "cover_up":
            ostr = "{},{},{},{}\n".format(a_s["code"], 5000, "nan", "fudge")
            fs.write(ostr)
        elif not a_s["code"] in found_codes:
            if config.verbose_level != VerboseLevel.NONE:
                print("Guessing formation thickness of", a_s["code"], "as", median_th)
            ostr = "{},{},{},{}\n".format(a_s["code"], median_th, "nan", "guess")
            fs.write(ostr)
    fs.close()

    new_asc = tidy_strat(config.tmp_path)
    new_asc.to_csv(
        os.path.join(config.tmp_path, "all_sorts_clean.csv"), index=None, header=True
    )


def tidy_strat(tmp_path):
    asg = pd.read_csv(os.path.join(tmp_path, "age_sorted_groups.csv"))
    asc = pd.read_csv(os.path.join(tmp_path, "all_sorts_clean.csv"))

    asg = asg.set_index("group_")
    if asc.group.str.contains("cover").any():  # add cover row if needed
        df = pd.DataFrame({"index": -1, "min": 0, "max": 0, "ave": 0}, index=["cover"])
        asg = pd.concat([df, asg])

    ave = asg.loc[asc.group]["ave"]  # get ave for each unit in asc
    ave = pd.DataFrame(ave)
    idx = pd.Index(range(len(ave)))
    ave = ave.set_index(idx)
    asc["ave"] = ave["ave"]  # set ave for each unit in asc

    new_asc = asc[asc.supergroup == "-99999999999999999xyz"]
    for (
        sg
    ) in (
        asc.supergroup.unique()
    ):  # crate new df with groups within supergroups sorted by age then index in group
        asc_sg = asc[asc.supergroup == sg]
        df2 = asc_sg.sort_values(["ave", "index in group"], ascending=[True, True])
        new_asc = pd.concat([new_asc, df2])

    sg_age = {}
    for sg in asc.supergroup.unique():  # calculate ave age of supergroup
        sga = asc[asc.supergroup == sg].ave.mean()
        sg_age[sg] = {"sg_ave": sga}

    sg_age_df = pd.DataFrame.from_dict(sg_age, orient="index")
    sg_age_df = sg_age_df.sort_values(
        "sg_ave"
    )  # create df with sorted ave age of supergroups

    new_asc2 = new_asc[new_asc.supergroup == "-99999999999999999xyz"]
    for (
        sg,
        age,
    ) in (
        sg_age_df.iterrows()
    ):  # create new df with supergroups sorted by age then index in group
        asc_sg = new_asc[new_asc.supergroup == sg]
        df2 = asc_sg.sort_values(["ave", "index in group"], ascending=[True, True])
        new_asc2 = pd.concat([new_asc2, df2])

    new_asc2 = new_asc2.drop("ave", axis=1)
    new_asc2 = new_asc2.reset_index()
    new_asc2 = new_asc2.drop("level_0", axis=1)
    new_asc2["index"] = new_asc2.index
    return new_asc2


####################################################
# calculate distance between two points (duplicate from m2l_utils??
####################################################


def xxxpt_dist(x1, y1, x2, y2):
    dist = sqrt(pow(x1 - x2, 2) + pow(y1 - y2, 2))
    return dist


####################################################
# determine if two bounding boxes overlap (not used currently)
####################################################


def bboxes_intersect(bbox1, bbox2):
    if (
        bbox1[0] <= bbox2[2]
        and bbox1[0] >= bbox2[0]
        and bbox1[1] <= bbox2[3]
        and bbox1[1] <= bbox2[1]
    ):
        return True
    elif (
        bbox1[0] <= bbox2[2]
        and bbox1[0] >= bbox2[0]
        and bbox1[3] <= bbox2[3]
        and bbox1[3] <= bbox2[1]
    ):
        return True
    elif (
        bbox1[2] <= bbox2[2]
        and bbox1[2] >= bbox2[0]
        and bbox1[1] <= bbox2[3]
        and bbox1[1] <= bbox2[1]
    ):
        return True
    elif (
        bbox1[2] <= bbox2[2]
        and bbox1[2] >= bbox2[0]
        and bbox1[3] <= bbox2[3]
        and bbox1[3] <= bbox2[1]
    ):
        return True
    elif (
        bbox2[0] <= bbox1[2]
        and bbox2[0] >= bbox1[0]
        and bbox2[3] <= bbox1[3]
        and bbox2[3] <= bbox1[1]
    ):
        return True
    else:
        return False


####################################
# Calculate local formation thickness estimates
#
# calc_thickness(tmp_path,output_path,buffer,max_thickness_allowed,c_l)
# Args:
# tmp_path path to temprorary file storage directory
# output_path path to m2l ouptuts directory
# buffer distance within which interpolated bedding orientations will be used for averaging
# max_thickness_allowed maximum valiud thickness (should be replaced by infinite search where no faults or fold axial traces are crossed
# c_l dictionary of codes and labels specific to input geo information layers
#
# Calculate local formation thickness estimates by finding intersection of normals to basal contacts
# with next upper formation in stratigraphy, and using interpolated orientaiton estimates to calculate true thickness
####################################


def calc_thickness(tmp_path, output_path, buffer, max_thickness_allowed, c_l):
    contact_points_file = os.path.join(tmp_path, "raw_contacts.csv")
    interpolated_combo_file = os.path.join(tmp_path, "combo_full.csv")
    # load basal contacts as geopandas dataframe
    contact_lines = gpd.read_file(os.path.join(tmp_path, "/basal_contacts.shp.zip"))
    all_sorts = pd.read_csv(os.path.join(tmp_path, "all_sorts.csv"))
    contacts = pd.read_csv(contact_points_file)
    orientations = pd.read_csv(interpolated_combo_file)
    olength = len(orientations)
    clength = len(contacts)
    cx = contacts["X"].to_numpy()

    cy = contacts["Y"].to_numpy()
    cl = contacts["lsx"].to_numpy(dtype=float)
    cm = contacts["lsy"].to_numpy(dtype=float)
    ctextcode = contacts["formation"].to_numpy()
    ox = orientations["X"].to_numpy()
    oy = orientations["Y"].to_numpy()
    dip = orientations["dip"].to_numpy().reshape(olength, 1)
    azimuth = orientations["azimuth"].to_numpy().reshape(olength, 1)

    l = np.zeros(len(ox))
    m = np.zeros(len(ox))
    n = np.zeros(len(ox))
    file = open(os.path.join(output_path, "formation_thicknesses.csv"), "w")
    file.write(
        "X,Y,formation,appar_th,thickness,cl,cm,meanl,meanm,meann,p1x,p1y,p2x,p2y,dip\n"
    )
    dist = m2l_interpolation.distance_matrix(ox, oy, cx, cy)

    # np.savetxt(os.path.join(tmp_path,'dist.csv'),dist,delimiter = ',')
    # display("ppp",cx.shape,cy.shape,ox.shape,oy.shape,dip.shape,azimuth.shape,dist.shape)
    n_est = 0
    for k in range(0, clength):  # loop through all contact segments
        a_dist = dist[:, k : k + 1]
        is_close = a_dist < buffer
        # display("ic",a_dist.shape,is_close.shape,dip.shape)
        close_dip = dip[is_close]
        # print("cd",close_dip.shape)
        # print(close_dip)
        close_azimuth = azimuth[is_close]
        n_good = 0
        for j in range(0, len(close_dip)):  # find averaged dips within buffer
            l[n_good], m[n_good], n[n_good] = m2l_utils.ddd2dircos(
                float(close_dip[j]), float(close_azimuth[j]) + 90.0
            )
            # print(k,len(close_dip),n_good,l[n_good],m[n_good],n[n_good])
            n_good = n_good + 1
        if n_good > 0:  # if we found any candidates
            # average direction cosine of points within buffer range
            lm = np.mean(l[:n_good])
            mm = np.mean(m[:n_good])
            nm = np.mean(n[:n_good])
            dip_mean, dipdirection_mean = m2l_utils.dircos2ddd(lm, mm, nm)
            # print(k,type(cm[k]),type(buffer))

            dx1 = -cm[k] * buffer
            dy1 = cl[k] * buffer
            dx2 = -dx1
            dy2 = -dy1
            p1 = Point((dx1 + cx[k], dy1 + cy[k]))
            p2 = Point((dx2 + cx[k], dy2 + cy[k]))
            ddline = LineString((p1, p2))
            orig = Point((cx[k], cy[k]))

            crossings = np.zeros((1000, 5))

            g = 0
            for indx, apair in all_sorts.iterrows():  # loop through all basal contacts
                if ctextcode[k] == apair["code"]:
                    # if(all_sorts.iloc[g]['group'] == all_sorts.iloc[g-1]['group']):
                    # subset contacts to just those with 'a' code
                    is_contacta = (
                        contact_lines["UNIT_NAME"] == all_sorts.iloc[g - 1]["code"]
                    )
                    acontacts = contact_lines[is_contacta]
                    i = 0
                    for (
                        ind,
                        acontact,
                    ) in (
                        acontacts.iterrows()
                    ):  # loop through distinct linestrings for upper contact
                        # if(bboxes_intersect(ddline.bounds,acontact[1].geometry.bounds)):
                        if not str(acontact.geometry) == "None":
                            if ddline.intersects(acontact.geometry):
                                isects = ddline.intersection(acontact.geometry)
                                if isects.geom_type == "MultiPoint":
                                    for pt in isects:
                                        if pt.distance(orig) < buffer * 2:
                                            # print(i,",", pt.x, ",",pt.y,",",apair[1]['code'],",",apair[1]['group'])
                                            crossings[i, 0] = i
                                            crossings[i, 1] = int(apair["index"])
                                            crossings[i, 2] = 0
                                            crossings[i, 3] = pt.x
                                            crossings[i, 4] = pt.y
                                            i = i + 1
                                else:
                                    if isects.distance(orig) < buffer * 2:
                                        # print(i,",", isects.x,",", isects.y,",",apair[1]['code'],",",apair[1]['group'])
                                        crossings[i, 0] = i
                                        crossings[i, 1] = int(apair["index"])
                                        crossings[i, 2] = 0
                                        crossings[i, 3] = isects.x
                                        crossings[i, 4] = isects.y
                                        i = i + 1

                                if (
                                    i > 0
                                ):  # if we found any intersections with base of next higher unit
                                    min_dist = 1e8
                                    # min_pt = 0
                                    for f in range(0, i):  # find closest hit
                                        this_dist = m2l_utils.ptsdist(
                                            crossings[f, 3],
                                            crossings[f, 4],
                                            cx[k],
                                            cy[k],
                                        )
                                        if this_dist < min_dist:
                                            min_dist = this_dist
                                            # min_pt = f
                                    # if not too far, add to output
                                    if min_dist < max_thickness_allowed:
                                        true_thick = sin(radians(dip_mean)) * min_dist
                                        ostr = "{},{},{},{},{},{},{},{},{},{},{},{},{},{},{}\n".format(
                                            cx[k],
                                            cy[k],
                                            ctextcode[k],
                                            min_dist,
                                            int(true_thick),
                                            cl[k],
                                            cm[k],
                                            lm,
                                            mm,
                                            nm,
                                            p1.x,
                                            p1.y,
                                            p2.x,
                                            p2.y,
                                            dip_mean,
                                        )
                                        # ostr = str(cx[k])+','+str(cy[k])+','+ctextcode[k]+','+str(int(true_thick))+\
                                        #    ','+str(cl[k])+','+str(cm[k])+','+str(lm)+','+str(mm)+','+str(nm)+','+\
                                        #    str(p1.x)+','+str(p1.y)+','+str(p2.x)+','+str(p2.y)+','+str(dip_mean)+'\n'
                                        file.write(ostr)
                                        n_est = n_est + 1

                g = g + 1
    print(
        n_est,
        "thickness estimates saved as",
        os.path.join(output_path, "formation_thicknesses.csv"),
    )


@beartype.beartype
def calc_thickness_with_grid(config: Config, map_data: MapData):
    contact_points_file = os.path.join(config.tmp_path, "raw_contacts.csv")
    dtm = map_data.get_map_data(Datatype.DTM).open()
    # load basal contacts as geopandas dataframe
    contact_lines = gpd.read_file(
        os.path.join(config.tmp_path, "basal_contacts.shp.zip")
    )
    all_sorts = pd.read_csv(os.path.join(config.tmp_path, "all_sorts.csv"))
    all_sorts["index2"] = all_sorts.index
    # all_sorts.set_index('code',inplace=True)
    geol = map_data.get_map_data(Datatype.GEOLOGY).copy()
    # geol=gpd.read_file(os.path.join(config.tmp_path, 'geol_clip.shp'))
    geol.drop_duplicates(subset="UNIT_NAME", inplace=True)
    # geol.set_index('UNIT_NAME',inplace=True)
    drops = geol[
        geol["DESCRIPTION"].str.contains(config.c_l["sill"])
        & geol["ROCKTYPE1"].str.contains(config.c_l["intrusive"])
    ]
    for ind, drop in drops.iterrows():
        all_sorts.drop(labels=drop.name, inplace=True, errors="ignore")
    all_sorts["code"] = all_sorts.index
    all_sorts["index"] = all_sorts["index2"]
    # all_sorts.set_index('index2',inplace=True)

    contacts = pd.read_csv(contact_points_file)

    clength = len(contacts)
    cx = contacts["X"].to_numpy()
    cy = contacts["Y"].to_numpy()
    cl = contacts["lsx"].to_numpy(dtype=float)
    cm = contacts["lsy"].to_numpy(dtype=float)
    ctextcode = contacts["formation"].to_numpy()

    fth = open(os.path.join(config.output_path, "formation_thicknesses.csv"), "w")
    fth.write(
        "X,Y,formation,appar_th,thickness,cl,cm,p1x,p1y,p2x,p2y,dip,type,slope_dip,slope_length,delz,zbase,zcross\n"
    )

    # np.savetxt(os.path.join(config.tmp_path,'dist.csv'),dist,delimiter = ',')
    # display("ppp",cx.shape,cy.shape,ox.shape,oy.shape,dip.shape,azimuth.shape,dist.shape)
    n_est = 0
    for k in range(0, clength):  # loop through all contact segments
        r = int((cy[k] - config.bbox[1]) / config.run_flags["interpolation_spacing"])
        c = int((cx[k] - config.bbox[0]) / config.run_flags["interpolation_spacing"])

        dip_mean = map_data.dip_grid[r, c]

        dx1 = -cm[k] * config.run_flags["thickness_buffer"]
        dy1 = cl[k] * config.run_flags["thickness_buffer"]
        dx2 = -dx1
        dy2 = -dy1
        p1 = Point((dx1 + cx[k], dy1 + cy[k]))
        p2 = Point((dx2 + cx[k], dy2 + cy[k]))
        ddline = LineString((p1, p2))
        orig = Point((cx[k], cy[k]))

        crossings = np.zeros((1000, 5))

        g = 0
        for indx, apair in all_sorts.iterrows():  # loop through all basal contacts
            if ctextcode[k] == apair["code"]:
                # subset contacts to just those with 'a' code
                is_contacta = (
                    contact_lines["UNIT_NAME"] == all_sorts.iloc[g - 1]["code"]
                )
                acontacts = contact_lines[is_contacta]
                i = 0
                for (
                    ind,
                    acontact,
                ) in (
                    acontacts.iterrows()
                ):  # loop through distinct linestrings for upper contact
                    # if(bboxes_intersect(ddline.bounds,acontact[1].geometry.bounds)):
                    if not str(acontact.geometry) == "None":
                        if ddline.intersects(acontact.geometry):
                            isects = ddline.intersection(acontact.geometry)
                            if isects.geom_type == "MultiPoint":
                                for pt in isects:
                                    if (
                                        pt.distance(orig)
                                        < config.run_flags["thickness_buffer"] * 2
                                    ):
                                        # print(i,",", pt.x, ",",pt.y,",",apair[1]['code'],",",apair[1]['group'])
                                        crossings[i, 0] = i
                                        crossings[i, 1] = int(apair["index"])
                                        crossings[i, 2] = 0
                                        crossings[i, 3] = pt.x
                                        crossings[i, 4] = pt.y
                                        i = i + 1
                            else:
                                if (
                                    isects.distance(orig)
                                    < config.run_flags["thickness_buffer"] * 2
                                ):
                                    # print(i,",", isects.x,",", isects.y,",",apair[1]['code'],",",apair[1]['group'])
                                    crossings[i, 0] = i
                                    crossings[i, 1] = int(apair["index"])
                                    crossings[i, 2] = 0
                                    crossings[i, 3] = isects.x
                                    crossings[i, 4] = isects.y
                                    i = i + 1

                            if (
                                i > 0
                            ):  # if we found any intersections with base of next higher unit
                                min_dist = 1e8
                                # min_pt = 0
                                for f in range(0, i):  # find closest hit
                                    this_dist = m2l_utils.ptsdist(
                                        crossings[f, 3], crossings[f, 4], cx[k], cy[k]
                                    )
                                    if this_dist < min_dist:
                                        min_dist = this_dist
                                        # min_pt = f
                                        crossx = crossings[f, 3]
                                        crossy = crossings[f, 4]
                                # if not too far, add to output
                                if (
                                    min_dist < config.run_flags["max_thickness_allowed"]
                                    and min_dist > 0
                                ):
                                    locations = [(cx[k], cy[k])]
                                    zbase = float(
                                        m2l_utils.value_from_dtm_dtb(
                                            dtm, "", "", False, locations
                                        )
                                    )
                                    locations = [(crossx, crossy)]
                                    zcross = float(
                                        m2l_utils.value_from_dtm_dtb(
                                            dtm, "", "", False, locations
                                        )
                                    )
                                    delz = fabs(zcross - zbase)
                                    slope_dip = degrees(atan(delz / min_dist))
                                    slope_length = sqrt(
                                        (min_dist * min_dist) + (delz * delz)
                                    )
                                    if slope_dip < dip_mean and zbase > zcross:
                                        surf_dip = dip_mean - slope_dip
                                    elif slope_dip < dip_mean and zbase < zcross:
                                        surf_dip = dip_mean + slope_dip
                                    elif slope_dip > dip_mean and zbase > zcross:
                                        surf_dip = slope_dip - dip_mean
                                    else:
                                        surf_dip = 180 - (dip_mean + slope_dip)

                                    true_thick = slope_length * sin(radians(surf_dip))
                                    if (
                                        not isnan(true_thick)
                                        and true_thick > 0
                                        and true_thick
                                        < config.run_flags["max_thickness_allowed"]
                                    ):
                                        ostr = "{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{}\n".format(
                                            cx[k],
                                            cy[k],
                                            ctextcode[k],
                                            min_dist,
                                            int(true_thick),
                                            cl[k],
                                            cm[k],
                                            p1.x,
                                            p1.y,
                                            p2.x,
                                            p2.y,
                                            dip_mean,
                                            "full",
                                            slope_dip,
                                            slope_length,
                                            delz,
                                            zbase,
                                            zcross,
                                        )
                                        # ostr = str(cx[k])+','+str(cy[k])+','+ctextcode[k]+','+str(int(true_thick))+\
                                        #    ','+str(cl[k])+','+str(cm[k])+','+str(lm)+','+str(mm)+','+str(nm)+','+\
                                        #    str(p1.x)+','+str(p1.y)+','+str(p2.x)+','+str(p2.y)+','+str(dip_mean)+'\n'
                                        fth.write(ostr)
                                        n_est = n_est + 1

            g = g + 1
    if config.verbose_level != VerboseLevel.NONE:
        print(
            n_est,
            "thickness estimates saved as",
            os.path.join(config.output_path, "formation_thicknesses.csv"),
        )


@beartype.beartype
def calc_min_thickness_with_grid(config: Config, map_data: MapData):
    dtm = map_data.get_map_data(Datatype.DTM).open()
    contact_points_file = os.path.join(config.tmp_path, "raw_contacts.csv")
    # load basal contacts as geopandas dataframe
    contact_lines = gpd.read_file(
        os.path.join(config.tmp_path, "basal_contacts.shp.zip")
    )
    all_sorts = pd.read_csv(os.path.join(config.tmp_path, "all_sorts.csv"))
    contacts = pd.read_csv(contact_points_file)

    sum_thick = pd.read_csv(
        os.path.join(config.output_path, "formation_thicknesses.csv")
    )
    found_codes = sum_thick["formation"].unique()
    if config.verbose_level != VerboseLevel.NONE:
        print(found_codes, "already processed")
    clength = len(contacts)
    cx = contacts["X"].to_numpy()
    cy = contacts["Y"].to_numpy()
    cl = contacts["lsx"].to_numpy(dtype=float)
    cm = contacts["lsy"].to_numpy(dtype=float)
    ctextcode = contacts["formation"].to_numpy()

    fth = open(os.path.join(config.output_path, "formation_thicknesses.csv"), "a+")
    # fth.write('X,Y,formation,appar_th,thickness,cl,cm,p1x,p1y,p2x,p2y,dip\n')

    # np.savetxt(os.path.join(config.tmp_path,'dist.csv'),dist,delimiter = ',')
    # display("ppp",cx.shape,cy.shape,ox.shape,oy.shape,dip.shape,azimuth.shape,dist.shape)
    n_est = 0
    for k in range(0, clength):  # loop through all contact segments
        if not (ctextcode[k] in found_codes):
            # print(ctextcode[k])
            r = int(
                (cy[k] - config.bbox[1]) / config.run_flags["interpolation_spacing"]
            )
            c = int(
                (cx[k] - config.bbox[0]) / config.run_flags["interpolation_spacing"]
            )

            dip_mean = map_data.dip_grid[r, c]

            dx1 = -cm[k] * config.run_flags["thickness_buffer"]
            dy1 = cl[k] * config.run_flags["thickness_buffer"]
            dx2 = -dx1
            dy2 = -dy1
            p1 = Point((dx1 + cx[k], dy1 + cy[k]))
            p2 = Point((dx2 + cx[k], dy2 + cy[k]))
            ddline = LineString((p1, p2))
            orig = Point((cx[k], cy[k]))

            crossings = np.zeros((1000, 5))

            g = 0
            for indx, apair in all_sorts.iterrows():  # loop through all basal contacts
                if ctextcode[k] == apair["code"]:
                    # subset contacts to just those with 'a' code
                    is_contacta = (
                        contact_lines["UNIT_NAME"] != all_sorts.iloc[g - 1]["code"]
                    )
                    acontacts = contact_lines[is_contacta]
                    i = 0
                    for (
                        ind,
                        acontact,
                    ) in (
                        acontacts.iterrows()
                    ):  # loop through distinct linestrings for upper contact
                        # if(bboxes_intersect(ddline.bounds,acontact[1].geometry.bounds)):

                        if not str(acontact.geometry) == "None":
                            if ddline.intersects(acontact.geometry):
                                isects = ddline.intersection(acontact.geometry)
                                if isects.geom_type == "MultiPoint":
                                    for pt in isects.geoms:
                                        if (
                                            pt.distance(orig)
                                            < config.run_flags["thickness_buffer"] * 2
                                        ):
                                            # print(i,",", pt.x, ",",pt.y,",",apair[1]['code'],",",apair[1]['group'])
                                            crossings[i, 0] = i
                                            crossings[i, 1] = int(apair["index"])
                                            crossings[i, 2] = 0
                                            crossings[i, 3] = pt.x
                                            crossings[i, 4] = pt.y
                                            i = i + 1
                                else:
                                    if not isects.geom_type == "GeometryCollection":
                                        if (
                                            isects.distance(orig)
                                            < config.run_flags["thickness_buffer"] * 2
                                        ):
                                            # print(i,",", isects.x,",", isects.y,",",apair[1]['code'],",",apair[1]['group'])
                                            crossings[i, 0] = i
                                            crossings[i, 1] = int(apair["index"])
                                            crossings[i, 2] = 0
                                            crossings[i, 3] = isects.x
                                            crossings[i, 4] = isects.y
                                            i = i + 1

                                if (
                                    i > 0
                                ):  # if we found any intersections with base of next higher unit
                                    min_dist = 1e8
                                    # min_pt = 0
                                    for f in range(0, i):  # find closest hit
                                        this_dist = m2l_utils.ptsdist(
                                            crossings[f, 3],
                                            crossings[f, 4],
                                            cx[k],
                                            cy[k],
                                        )
                                        if this_dist < min_dist:
                                            min_dist = this_dist
                                            # min_pt = f
                                            crossx = crossings[f, 3]
                                            crossy = crossings[f, 4]
                                    # if not too far, add to output
                                    if (
                                        min_dist
                                        < config.run_flags["max_thickness_allowed"]
                                        and min_dist > 1
                                    ):
                                        locations = [(cx[k], cy[k])]
                                        zbase = float(
                                            m2l_utils.value_from_dtm_dtb(
                                                dtm, "", "", False, locations
                                            )
                                        )
                                        locations = [(crossx, crossy)]
                                        zcross = float(
                                            m2l_utils.value_from_dtm_dtb(
                                                dtm, "", "", False, locations
                                            )
                                        )
                                        delz = fabs(zcross - zbase)
                                        slope_dip = degrees(atan(delz / min_dist))
                                        slope_length = sqrt(
                                            (min_dist * min_dist) + (delz * delz)
                                        )
                                        if slope_dip < dip_mean and zbase > zcross:
                                            surf_dip = dip_mean - slope_dip
                                        elif slope_dip < dip_mean and zbase < zcross:
                                            surf_dip = dip_mean + slope_dip
                                        elif slope_dip > dip_mean and zbase > zcross:
                                            surf_dip = slope_dip - dip_mean
                                        else:
                                            surf_dip = 180 - (dip_mean + slope_dip)

                                        true_thick = slope_length * sin(
                                            radians(surf_dip)
                                        )
                                        if (
                                            not isnan(true_thick)
                                            and true_thick > 0
                                            and true_thick
                                            < config.run_flags["max_thickness_allowed"]
                                        ):
                                            ostr = "{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{}\n".format(
                                                cx[k],
                                                cy[k],
                                                ctextcode[k],
                                                min_dist,
                                                int(true_thick),
                                                cl[k],
                                                cm[k],
                                                p1.x,
                                                p1.y,
                                                p2.x,
                                                p2.y,
                                                dip_mean,
                                                "min",
                                                slope_dip,
                                                slope_length,
                                                delz,
                                                zbase,
                                                zcross,
                                            )
                                            # ostr = str(cx[k])+','+str(cy[k])+','+ctextcode[k]+','+str(int(true_thick))+\
                                            #    ','+str(cl[k])+','+str(cm[k])+','+str(lm)+','+str(mm)+','+str(nm)+','+\
                                            #    str(p1.x)+','+str(p1.y)+','+str(p2.x)+','+str(p2.y)+','+str(dip_mean)+'\n'
                                            fth.write(ostr)
                                            n_est = n_est + 1

            g = g + 1
    if config.verbose_level != VerboseLevel.NONE:
        print(
            n_est,
            "min thickness estimates appended to",
            os.path.join(config.output_path, "formation_thicknesses.csv"),
        )
    fth.close()


####################################
# Normalise thickness for each estimate to median for that formation
#
# normalise_thickness(output_path)
# Args:
# output_path path to m2l output directory
#
# Normalises previously calculated formation thickness by dviding by median value for that formation
####################################
def normalise_thickness(output_path):
    thickness = pd.read_csv(
        os.path.join(output_path, "formation_thicknesses.csv"), sep=","
    )

    codes = thickness.formation.unique()
    f = open(os.path.join(output_path, "formation_thicknesses_norm.csv"), "w")
    f.write("x,y,formation,app_th,thickness,norm_th\n")
    fs = open(os.path.join(output_path, "formation_summary_thicknesses.csv"), "w")
    fs.write("formation,thickness median,thickness std,method\n")
    for code in codes:
        is_code = thickness.formation.str.contains(code, regex=False)
        all_thick = thickness[is_code]
        all_thick2 = all_thick[all_thick["thickness"] != 0]
        thicknesses = np.asarray(all_thick2.loc[:, "thickness"], dtype=float)

        if len(all_thick2) > 2:
            med = np.median(thicknesses)
            std = np.std(thicknesses)
            # print(code, med, std)
            ostr = "{},{},{},{}\n".format(code, med, std, all_thick2.iloc[0]["type"])
            # ostr = str(code)+","+str(all_thick2.loc[:,"thickness"].median())+","+str(all_thick2.loc[:,"thickness"].std())+"\n"
            fs.write(ostr)

            thick = all_thick2.to_numpy()

            for i in range(len(thick)):
                if med > 0:
                    ostr = "{},{},{},{},{},{}\n".format(
                        thick[i, 0],
                        thick[i, 1],
                        thick[i, 2],
                        thick[i, 3],
                        thick[i, 4],
                        thicknesses[i] / med,
                    )
                    # ostr = str(thick[i,0])+","+str(thick[i,1])+","+str(thick[i,2])+","+str(thick[i,3])+","+str(thick[i,3]/med)+"\n"
                    f.write(ostr)
    f.close()
    fs.close()


####################################################
# Save out near-fold axial trace orientations:
# save_fold_axial_traces_orientations(path_folds,output_path,tmp_path,dtm,c_l,dst_crs,fold_decimate,fat_step,close_dip)
# Args:
# path_faults path to clipped fold axial trace layer
# path_fault_orientations directory for outputs
# dtm rasterio format elevation grid
# c_l dictionary of codes and labels specific to input geo information layers
# fault_decimate decimation factor for saving every nth input point on fault polylines

###################################################


@beartype.beartype
def save_fold_axial_traces_orientations(
    config: Config, map_data: MapData, workflow: dict
):
    dtm = map_data.get_map_data(Datatype.DTM).open()
    geology = gpd.read_file(os.path.join(config.tmp_path, "geol_clip.shp"))
    # contacts = np.genfromtxt(os.path.join(config.tmp_path,'interpolation_contacts_'+config.run_flags['interpolation_scheme']+'.csv'),delimiter = ',',dtype = 'float')
    f = open(
        os.path.join(config.output_path, "fold_axial_trace_orientations2.csv"), "w"
    )
    f.write("X,Y,Z,azimuth,dip,polarity,formation,group\n")
    folds_clip = map_data.get_map_data(Datatype.FOLD).copy()
    # folds_clip = gpd.read_file(path_folds,)
    folds_clip = folds_clip.dropna(subset=["geometry"])
    fo = open(os.path.join(config.output_path, "fold_axial_traces.csv"), "w")
    fo.write("X,Y,Z,code,type\n")
    dummy = []
    dummy.append(1)
    for indx, fold in folds_clip.iterrows():
        fold_name = str(fold["GEOMETRY_OBJECT_ID"])
        if not str(fold.geometry.type) == "None":
            if fold.geometry.type == "MultiLineString":
                for mls in fold.geometry:
                    fold_ls = LineString(mls)

                    i = 0
                    first = True
                    for afs in fold_ls.coords:
                        if config.c_l["fold"].lower() in fold["FEATURE"].lower():
                            # save out current geometry of FAT
                            # decimate to reduce number of points, but also take mid and end points of a series to keep some shape
                            if (
                                i % config.run_flags["fold_decimate"] == 0
                                or i == int((len(fold_ls.coords) - 1) / 2)
                                or i == len(fold_ls.coords) - 1
                            ):
                                locations = [(afs[0], afs[1])]
                                height = m2l_utils.value_from_dtm_dtb(
                                    dtm,
                                    map_data.dtb,
                                    map_data.dtb_null,
                                    workflow["cover_map"],
                                    locations,
                                )
                                ostr = "{},{},{},FA_{},{}\n".format(
                                    afs[0],
                                    afs[1],
                                    height,
                                    fold_name,
                                    fold["TYPE"].replace(",", ""),
                                )
                                # ostr = str(afs[0])+','+str(afs[1])+','+str(height)+','+'FA_'+fold_name+','+fold['TYPE'].replace(',','')+'\n'
                                fo.write(ostr)
                                # calculate FAT normal offsets
                                first = False
                                lastx = afs[0]
                                lasty = afs[1]
                                if not first:
                                    l, m = m2l_utils.pts2dircos(
                                        lastx, lasty, afs[0], afs[1]
                                    )
                                    midx = lastx + ((afs[0] - lastx) / 2)
                                    midy = lasty + ((afs[1] - lasty) / 2)
                                    midxr = midx + (config.run_flags["fat_step"] * -m)
                                    midyr = midy + (config.run_flags["fat_step"] * l)
                                    midxl = midx - (config.run_flags["fat_step"] * -m)
                                    midyl = midy - (config.run_flags["fat_step"] * l)
                                    r = int(
                                        (midy - config.bbox[1])
                                        / config.run_flags["interpolation_spacing"]
                                    )
                                    c = int(
                                        (midx - config.bbox[0])
                                        / config.run_flags["interpolation_spacing"]
                                    )
                                    if config.run_flags["close_dip"] == -999:
                                        dip = map_data.dip_grid[r, c]
                                    else:
                                        dip = config.run_flags["close_dip"]
                                    dip_dir = map_data.dip_dir_grid[r, c]

                                    dip2, dipdir2 = m2l_utils.dircos2ddd(
                                        -m, l, cos(radians(dip))
                                    )
                                    if config.c_l["syn"] in fold["TYPE"]:
                                        dipdir2 = dipdir2 + 180

                                    lc = sin(radians(dip_dir - 90))
                                    mc = cos(radians(dip_dir - 90))
                                    dotprod = fabs((l * lc) + (m * mc))
                                    # print(dotprod,midx,midy,minind,contacts[minind,2],l,m,lc,mc)
                                    # if FAT is sub-parallel to local interpolated contacts, save out as orientations
                                    if dotprod > 0.85:
                                        geometry = [Point(midxr, midyr)]
                                        gdf = gpd.GeoDataFrame(
                                            dummy,
                                            crs=map_data.working_projection,
                                            geometry=geometry,
                                        )
                                        structure_code = gpd.sjoin(
                                            gdf, geology, how="left", predicate="within"
                                        )
                                        if (
                                            not str(structure_code.iloc[0]["UNIT_NAME"])
                                            == "nan"
                                        ):
                                            locations = [(midxr, midyr)]
                                            height = m2l_utils.value_from_dtm_dtb(
                                                dtm,
                                                map_data.dtb,
                                                map_data.dtb_null,
                                                workflow["cover_map"],
                                                locations,
                                            )
                                            ostr = "{},{},{},{},{},{},{},{}\n".format(
                                                midxr,
                                                midyr,
                                                height,
                                                dipdir2,
                                                int(dip),
                                                1,
                                                str(structure_code.iloc[0]["UNIT_NAME"])
                                                .replace(" ", "_")
                                                .replace("-", "_"),
                                                structure_code.iloc[0]["GROUP"],
                                            )
                                            # ostr = str(midxr)+','+str(midyr)+','+str(height)+','+str(dipdir)+','+str(int(dip))+',1,'+str(structure_code.iloc[0]['UNIT_NAME']).replace(" ","_").replace("-","_")+','+str(structure_code.iloc[0]['GROUP])+'\n'
                                            f.write(ostr)

                                        geometry = [Point(midxl, midyl)]
                                        gdf = gpd.GeoDataFrame(
                                            dummy,
                                            crs=map_data.working_projection,
                                            geometry=geometry,
                                        )
                                        structure_code = gpd.sjoin(
                                            gdf, geology, how="left", predicate="within"
                                        )
                                        if (
                                            not str(structure_code.iloc[0]["UNIT_NAME"])
                                            == "nan"
                                        ):
                                            locations = [(midxl, midyl)]
                                            height = m2l_utils.value_from_dtm_dtb(
                                                dtm,
                                                map_data.dtb,
                                                map_data.dtb_null,
                                                workflow["cover_map"],
                                                locations,
                                            )
                                            ostr = "{},{},{},{},{},{},{},{}\n".format(
                                                midxl,
                                                midyl,
                                                height,
                                                dipdir2 + 180,
                                                int(dip),
                                                1,
                                                str(structure_code.iloc[0]["UNIT_NAME"])
                                                .replace(" ", "_")
                                                .replace("-", "_"),
                                                structure_code.iloc[0]["GROUP"],
                                            )
                                            # ostr = str(midxl)+','+str(midyl)+','+str(height)+','+str(dipdir+180)+','+str(int(dip))+',1,'+str(structure_code.iloc[0]['UNIT_NAME']).replace(" ","_").replace("-","_")+','+str(structure_code.iloc[0]['GROUP'])+'\n'
                                            f.write(ostr)

                        i = i + 1
            else:
                fold_ls = LineString(fold.geometry)
                i = 0
                first = True
                for afs in fold_ls.coords:
                    if config.c_l["fold"].lower() in fold["FEATURE"].lower():
                        # save out current geometry of FAT
                        # decimate to reduce number of points, but also take mid and end points of a series to keep some shape
                        if (
                            i % config.run_flags["fold_decimate"] == 0
                            or i == int((len(fold_ls.coords) - 1) / 2)
                            or i == len(fold_ls.coords) - 1
                        ):
                            locations = [(afs[0], afs[1])]
                            height = m2l_utils.value_from_dtm_dtb(
                                dtm,
                                map_data.dtb,
                                map_data.dtb_null,
                                workflow["cover_map"],
                                locations,
                            )
                            ostr = "{},{},{},FA_{},{}\n".format(
                                afs[0],
                                afs[1],
                                height,
                                fold_name,
                                fold["TYPE"].replace(",", ""),
                            )
                            # ostr = str(afs[0])+','+str(afs[1])+','+str(height)+','+'FA_'+fold_name+','+fold['TYPE'].replace(',','')+'\n'
                            fo.write(ostr)
                            # calculate FAT normal offsets
                            if not first:
                                l, m = m2l_utils.pts2dircos(
                                    lastx, lasty, afs[0], afs[1]
                                )
                                midx = lastx + ((afs[0] - lastx) / 2)
                                midy = lasty + ((afs[1] - lasty) / 2)
                                midxr = midx + (config.run_flags["fat_step"] * -m)
                                midyr = midy + (config.run_flags["fat_step"] * l)
                                midxl = midx - (config.run_flags["fat_step"] * -m)
                                midyl = midy - (config.run_flags["fat_step"] * l)
                                r = int(
                                    (midy - config.bbox[1])
                                    / config.run_flags["interpolation_spacing"]
                                )
                                c = int(
                                    (midx - config.bbox[0])
                                    / config.run_flags["interpolation_spacing"]
                                )
                                if config.run_flags["close_dip"] == -999:
                                    dip = map_data.dip_grid[r, c]
                                else:
                                    dip = config.run_flags["close_dip"]
                                dipdir = map_data.dip_dir_grid[r, c]
                                dip2, dipdir2 = m2l_utils.dircos2ddd(
                                    -m, l, cos(radians(dip))
                                )
                                if config.c_l["syn"] in fold["TYPE"]:
                                    dipdir2 = dipdir2 + 180
                                lc = sin(radians(dipdir - 90))
                                mc = cos(radians(dipdir - 90))
                                dotprod = fabs((l * lc) + (m * mc))
                                # print(dotprod,midx,midy,minind,contacts[minind,2],l,m,lc,mc)
                                # if FAT is sub-parallel to local interpolated contacts, save out as orientations
                                if dotprod > 0.85:
                                    geometry = [Point(midxr, midyr)]
                                    gdf = gpd.GeoDataFrame(
                                        dummy,
                                        crs=map_data.working_projection,
                                        geometry=geometry,
                                    )
                                    structure_code = gpd.sjoin(
                                        gdf, geology, how="left", predicate="within"
                                    )
                                    if (
                                        not str(structure_code.iloc[0]["UNIT_NAME"])
                                        == "nan"
                                    ):
                                        locations = [(midxr, midyr)]
                                        height = m2l_utils.value_from_dtm_dtb(
                                            dtm,
                                            map_data.dtb,
                                            map_data.dtb_null,
                                            workflow["cover_map"],
                                            locations,
                                        )
                                        ostr = "{},{},{},{},{},{},{},{}\n".format(
                                            midxr,
                                            midyr,
                                            height,
                                            dipdir2,
                                            int(dip),
                                            1,
                                            str(structure_code.iloc[0]["UNIT_NAME"])
                                            .replace(" ", "_")
                                            .replace("-", "_"),
                                            structure_code.iloc[0]["GROUP"],
                                        )
                                        # ostr = str(midxr)+','+str(midyr)+','+str(height)+','+str(dipdir)+','+str(int(dip))+',1,'+str(structure_code.iloc[0]['UNIT_NAME']).replace(" ","_").replace("-","_")+','+str(structure_code.iloc[0]['GROUP'])+'\n'
                                        f.write(ostr)

                                    geometry = [Point(midxl, midyl)]
                                    gdf = gpd.GeoDataFrame(
                                        dummy,
                                        crs=map_data.working_projection,
                                        geometry=geometry,
                                    )
                                    structure_code = gpd.sjoin(
                                        gdf, geology, how="left", predicate="within"
                                    )
                                    if (
                                        not str(structure_code.iloc[0]["UNIT_NAME"])
                                        == "nan"
                                    ):
                                        locations = [(midxl, midyl)]
                                        height = m2l_utils.value_from_dtm_dtb(
                                            dtm,
                                            map_data.dtb,
                                            map_data.dtb_null,
                                            workflow["cover_map"],
                                            locations,
                                        )
                                        ostr = "{},{},{},{},{},{},{},{}\n".format(
                                            midxl,
                                            midyl,
                                            height,
                                            dipdir2 + 180,
                                            int(dip),
                                            1,
                                            str(structure_code.iloc[0]["UNIT_NAME"])
                                            .replace(" ", "_")
                                            .replace("-", "_"),
                                            structure_code.iloc[0]["GROUP"],
                                        )
                                        # ostr = str(midxl)+','+str(midyl)+','+str(height)+','+str(dipdir+180)+','+str(int(dip))+',1,'+str(structure_code.iloc[0]['UNIT_NAME']).replace(" ","_").replace("-","_")+','+str(structure_code.iloc[0]['GROUP'])+'\n'
                                        f.write(ostr)
                            first = False
                            lastx = afs[0]
                            lasty = afs[1]
                    i = i + 1

    fo.close()
    f.close()
    if config.verbose_level != VerboseLevel.NONE:
        print(
            "fold axial traces saved as",
            os.path.join(config.output_path, "fold_axial_traces.csv"),
        )
        print(
            "fold axial trace orientations saved as",
            os.path.join(config.output_path, "fold_axial_trace_orientations.csv"),
        )


####################################################
# Convert XZ section information to XY Model coordinates:
# section2model(seismic_line,seismic_bbox,sx,sy)
# Args:
# seismic_line geopandas object showing surface trace of seismic line
# seismic_bbox geopandas object defining TL,TR and BR coordinates of seismic interp
# sx,sy XZ coordinates of a posiiton in the section
# returns XY coordinates in model space
###################################################


def section2model(seismic_line, seismic_bbox, sx, sy):
    sx1 = (sx - seismic_bbox.loc["TL"].geometry.x) / (
        seismic_bbox.loc["TR"].geometry.x - seismic_bbox.loc["TL"].geometry.x
    )
    # sy1 = sy - seismic_bbox.loc["TR"].geometry.y
    for indx, lines in seismic_line.iterrows():
        s_ls = LineString(lines.geometry)
        full_dist = s_ls.length
        break

    for indx, lines in seismic_line.iterrows():
        s_ls = LineString(lines.geometry)
        first = True
        cdist = 0
        for seg in s_ls.coords:
            first = False
            lsegx = seg[0]
            lsegy = seg[1]
            last_norm_dist = 0
            if not first:
                dist = m2l_utils.ptsdist(seg[0], seg[1], lsegx, lsegy)
                cdist = cdist + dist
                norm_dist = cdist / full_dist
                if sx1 > last_norm_dist and sx1 < norm_dist:
                    local_norm = (sx1 - last_norm_dist) / (norm_dist - last_norm_dist)
                    mx = lsegx + ((seg[0] - lsegx) * local_norm)
                    my = lsegy + ((seg[1] - lsegy) * local_norm)
                    return (mx, my)
                lsegx = seg[0]
                lsegy = seg[1]
                last_norm_dist = norm_dist

        return (-999, -999)


####################################################
# Extract fault and group stratigraphy information from section:
# extract_section(tmp_path,output_path,seismic_line,seismic_bbox,seismic_interp,dtm,surface_cut)
# Args:
# tmp_path path to tmp directory
# output_path path to output directory
# seismic_line geopandas object showing surface trace of seismic line
# seismic_bbox geopandas object defining TL,TR and BR coordinates of seismic interp
# seismic_interp geopandas object containing interreted faults and strat surfaces as polylines
# dtm projected dtm grid as rasterio object
# surface_cut shallowest level to extract from section (in section metre coordinates)
###################################################


@beartype.beartype
def extract_section(
    config: Config,
    map_data,
    workflow: dict,
    seismic_line,
    seismic_bbox,
    seismic_interp,
    surface_cut=2000,
):
    faults = map_data.get_map_data(Datatype.FAULT)
    dtm = map_data.get_map_data(Datatype.DTM).open()
    all_sorts = pd.read_csv(os.path.join(config.tmp_path, "all_sorts2.csv"), sep=",")
    sf = open(os.path.join(config.output_path, "seismic_faults.csv"), "w")
    sf.write("X,Y,Z,formation\n")
    sb = open(os.path.join(config.output_path, "seismic_base.csv"), "w")
    sb.write("X,Y,Z,formation\n")
    for indx, interps in seismic_interp.iterrows():
        i_ls = LineString(interps.geometry)
        for seg in i_ls.coords:
            mx, my = section2model(seismic_line, seismic_bbox, seg[0], seg[1])
            if mx != -999 and my != -999:
                mz = (
                    seismic_bbox.loc["BR"]["DEPTH"]
                    * (seismic_bbox.loc["TR"].geometry.y - seg[1])
                    / (
                        seismic_bbox.loc["TR"].geometry.y
                        - seismic_bbox.loc["BR"].geometry.y
                    )
                )
                locations = [(mx, my)]
                height = m2l_utils.value_from_dtm_dtb(
                    dtm,
                    map_data.dtb,
                    map_data.dtb_null,
                    workflow["cover_map"],
                    locations,
                )
                if not height == -999 and mz > surface_cut:
                    mz2 = -mz + float(height)
                    # print(mx,my,mz,height,mz2)
                    if str(interps["IDENT"]) == "None":
                        ident = "None"
                    else:
                        ident = str(interps["IDENT"])
                    if "Base" in interps["FEATURE"]:
                        maxfm = 0
                        maxname = ""
                        for indx, formation in all_sorts.iterrows():
                            if (
                                formation["group"] in interps["IDENT"]
                                and formation["index in group"] > maxfm
                            ):
                                maxfm = formation["index in group"]
                                maxname = formation["code"]
                        ostr = "{},{},{},{}\n".format(mx, my, mz2, maxname)
                        # ostr = str(mx)+','+str(my)+','+str(mz2)+','+maxname+'\n'
                        sb.write(ostr)
                    else:
                        for indx, aflt in faults.iterrows():
                            if not str(aflt["NAME"]) == "None" and not ident == "None":
                                fname = aflt["NAME"].replace(" ", "_")
                                if fname in interps["IDENT"]:
                                    fault_id = "Fault_" + str(aflt["OBJECTID"])
                                    ostr = "{},{},{},{}\n".format(mx, my, mz2, fault_id)
                                    # ostr = str(mx)+','+str(my)+','+str(mz2)+','+fault_id+'\n'
                                    sf.write(ostr)
                                    break
    sf.close()
    sb.close()


####################################################
# Calculate polarity of bedding:
# save_orientations_with_polarity(orientations_path,path_out,c_l,basal_path,all_sorts_path)
# Args:
# orientations_path path to orientations file
# path_out path to output directory
# c_l dictionary of codes and labels specific to input geo information layers
# basal_path path to basal contacts file
# all_sorts_path path to all_sorted_formations file
#
# -999 means couldn't calculate polarity
# 0 means inverted
# 1 means normal polarity
###################################################


@beartype.beartype
def save_orientations_with_polarity(config: Config, map_data: MapData):
    buffer = 10000
    contact_lines = gpd.read_file(
        os.path.join(config.tmp_path, "basal_contacts.shp.zip")
    )
    all_sorts = pd.read_csv(os.path.join(config.tmp_path, "all_sorts.csv"), sep=",")
    orientations = pd.read_csv(
        os.path.join(config.output_path, "orientations.csv"), sep=","
    )
    codes = all_sorts["code"].unique()
    # all_sorts.set_index('code',  inplace=True)

    f = open(os.path.join(config.output_path, "orientations_polarity.csv"), "w")
    f.write("X,Y,Z,azimuth,dip,polarity,formation\n")

    for indx, anori in orientations.iterrows():  # loop through orientations
        l, m, n = m2l_utils.ddd2dircos(
            float(anori["dip"]), float(anori["azimuth"]) + 90.0
        )
        l2 = l / sqrt((l * l) + (m * m))
        m2 = m / sqrt((l * l) + (m * m))

        dx1 = 0
        dy1 = 0
        dx2 = m2 * buffer
        dy2 = -l2 * buffer
        p1 = Point((dx1 + float(anori["X"]), dy1 + float(anori["Y"])))
        p2 = Point((dx2 + float(anori["X"]), dy2 + float(anori["Y"])))
        ddline = LineString((p1, p2))
        orig = Point((float(anori["X"]), float(anori["Y"])))

        close_dist = 1e9
        close_fm = ""
        # close_x = 0
        # close_y = 0

        for (
            indx2,
            acontact,
        ) in contact_lines.iterrows():  # loop through distinct linestrings dipdir +180
            if acontact["UNIT_NAME"] in codes:
                if not str(acontact.geometry) == "None":
                    isects = ddline.intersection(acontact.geometry)
                    if isects.geom_type == "MultiPoint":
                        for pt in isects:
                            if pt.distance(orig) < buffer * 2:
                                dist = m2l_utils.ptsdist(
                                    float(anori["X"]), float(anori["Y"]), pt.x, pt.y
                                )
                                if dist < close_dist:
                                    close_dist = dist
                                    close_fm = acontact["UNIT_NAME"]
                                    # close_x = pt.x
                                    # close_y = pt.y
                                    sign = 1
                    elif isects.geom_type == "Point":
                        if isects.distance(orig) < buffer * 2:
                            dist = m2l_utils.ptsdist(
                                float(anori["X"]), float(anori["Y"]), isects.x, isects.y
                            )
                            if dist < close_dist:
                                close_dist = dist
                                close_fm = acontact["UNIT_NAME"]
                                # close_x = isects.x
                                # close_y = isects.y
                                sign = 1

        dx2 = -m2 * buffer
        dy2 = l2 * buffer
        p1 = Point((dx1 + float(anori["X"]), dy1 + float(anori["Y"])))
        p2 = Point((dx2 + float(anori["X"]), dy2 + float(anori["Y"])))
        ddline = LineString((p1, p2))

        for (
            indx2,
            acontact,
        ) in contact_lines.iterrows():  # loop through distinct linestrings dipdir
            if acontact["UNIT_NAME"] in codes:
                if not str(acontact.geometry) == "None":
                    isects = ddline.intersection(acontact.geometry)
                    if isects.geom_type == "MultiPoint":
                        for pt in isects:
                            if pt.distance(orig) < buffer * 2:
                                dist = m2l_utils.ptsdist(
                                    float(anori["X"]), float(anori["Y"]), pt.x, pt.y
                                )
                                if dist < close_dist:
                                    close_dist = dist
                                    close_fm = acontact["UNIT_NAME"]
                                    # close_x = pt.x
                                    # close_y = pt.y
                                    sign = 0
                    elif isects.geom_type == "Point":
                        if isects.distance(orig) < buffer * 2:
                            dist = m2l_utils.ptsdist(
                                float(anori["X"]), float(anori["Y"]), isects.x, isects.y
                            )
                            if dist < close_dist:
                                close_dist = dist
                                close_fm = acontact["UNIT_NAME"]
                                # close_x = isects.x
                                # close_y = isects.y
                                sign = 0

        if not close_fm == "":
            # print(sign,anori["formation"],close_fm,int(all_sorts.loc[anori["formation"]]["index"]),int(all_sorts.loc[close_fm]["index"]))
            if sign == 1:
                if (
                    int(all_sorts.loc[anori["formation"]]["index"])
                    <= int(all_sorts.loc[close_fm]["index"])
                    and close_dist < buffer * 2
                ):
                    polarity = 1
                else:
                    polarity = 0
            else:
                if (
                    int(all_sorts.loc[anori["formation"]]["index"])
                    < int(all_sorts.loc[close_fm]["index"])
                    and close_dist < buffer * 2
                ):
                    polarity = 0
                else:
                    polarity = 1
        else:  # failed to find contact close enough defined by buffer
            polarity = -999
        ostr = "{},{},{},{},{},{},{}\n".format(
            anori["X"],
            anori["Y"],
            anori["Z"],
            anori["azimuth"],
            anori["dip"],
            polarity,
            anori["formation"],
        )
        # ostr = str(anori['X'])+","+str(anori['Y'])+","+str(anori['Z'])+","+str(anori['azimuth'])+","+str(anori['dip'])+","+str(polarity)+","+str(anori['formation'])+"\n"
        f.write(ostr)
    f.close()
    if config.verbose_level != VerboseLevel.NONE:
        print(
            "orientations saved to",
            os.path.join(config.output_path, "orientations_polarity.csv"),
        )


####################################################
# Calculate stratigraphic and absolute minimum stratigraphic offset of faults:
# fault_strat_offset(path_out,c_l,dst_crs,fm_thick_file, all_sorts_file,fault_file,geol_file,fault_dim_file)# Args:
# orientations_path path to orientations file
# path_out path to output directory
# c_l dictionary of codes and labels specific to input geo information layers
# dst_crs Coordinate Reference System of vector files
# fm_thick_file path to summary formation thicknesses file
# faults is a geoDataFrame containing the faults
# geology is a geoDataFrame containg the geology
# fault_dim_file path to fault dimensions file
#
# Stratigraphic offset is the difference in stratigraphically sorted indices of formations across a fault
# Absolute minimum stratigraphic ossfet is based on the calculated formation thicknesses seprarating two units across a fault
###################################################
@beartype.beartype
def fault_strat_offset(config: Config, map_data: MapData):
    fm_thick = pd.read_csv(
        os.path.join(config.output_path, "formation_summary_thicknesses.csv"),
        sep=",",
        index_col=False,
    )
    formations = fm_thick["formation"].unique()
    all_sorts = pd.read_csv(os.path.join(config.tmp_path, "all_sorts.csv"), sep=",")
    codes = all_sorts["code"].unique()
    local_faults = map_data.get_map_data(Datatype.FAULT).copy()
    local_geology = map_data.get_map_data(Datatype.GEOLOGY).copy()

    als_thick = [
        [
            "index",
            "group number",
            "index in group",
            "number in group",
            "code",
            "group",
            "uctype",
            "thickness median",
        ]
    ]
    index = 0
    for ias, als in all_sorts.iterrows():
        found = False
        for ifm, fm in fm_thick.iterrows():
            if als["code"] == fm["formation"]:
                als_thick += [
                    [
                        index,
                        als["group number"],
                        als["index in group"],
                        als["number in group"],
                        als["code"],
                        als["group"],
                        "erode",
                        fm["thickness median"],
                    ]
                ]
                index = index + 1
                found = True
                break
        if not found:
            als_thick += [
                [
                    index,
                    als["group number"],
                    als["index in group"],
                    als["number in group"],
                    als["code"],
                    als["group"],
                    "erode",
                    0,
                ]
            ]
            index = index + 1

    column_names = als_thick.pop(0)
    new_als = pd.DataFrame(als_thick, columns=column_names)
    fm_no = len(new_als)

    # create and fill array proving mimimum displacement for all possible strat combinations
    fm_thick_arr = np.zeros((fm_no, fm_no))

    for i in range(0, fm_no - 1):
        thick_diff = 0
        fm_thick_arr[i, 0] = 0
        fm_thick_arr[i, 1] = 0

        for j in range(i + 1, fm_no - 1):
            thick_diff = thick_diff + new_als.iloc[j]["thickness median"]
            fm_thick_arr[i, j + 1] = thick_diff

    np.savetxt(
        os.path.join(config.output_path, "fault_strat_offset_array.csv"),
        fm_thick_arr,
        delimiter=",",
    )

    new_als.set_index("code", inplace=True)

    all_long_faults = np.genfromtxt(
        os.path.join(config.output_path, "fault_dimensions.csv"),
        delimiter=",",
        dtype="U100",
    )

    data = []
    columns = ["X", "Y", "id", "left_fm", "right_fm", "min_offset", "strat_offset"]
    if len(all_long_faults) > 0:
        fault_names = all_long_faults[1:, :1]

        if config.verbose_level != VerboseLevel.NONE:
            print(
                "Calculating fault stratigraphic offsets for",
                len(local_faults),
                "faults",
            )

        # Create lists of fault segment mid points, and points 10m to the left and right of the
        # mid points, also build a corresponding list of faultIds for those points
        lgeomList = []
        rgeomList = []
        xmidsList = []
        ymidsList = []
        faultIds = []
        for index, fault in local_faults.iterrows():
            if "Fault_" + str(fault["GEOMETRY_OBJECT_ID"]) in fault_names:
                L = fault.geometry.coords
                avg = lambda x0, x1: (x0 + x1) / 2
                xmids = [
                    avg(pts[0][0], pts[1][0])
                    for pts in [L[index : index + 2] for index in range(len(L) - 1)]
                ]
                ymids = [
                    avg(pts[0][1], pts[1][1])
                    for pts in [L[index : index + 2] for index in range(len(L) - 1)]
                ]
                xdiffs = [
                    pts[1][0] - pts[0][0]
                    for pts in [L[index : index + 2] for index in range(len(L) - 1)]
                ]
                ydiffs = [
                    pts[1][1] - pts[0][1]
                    for pts in [L[index : index + 2] for index in range(len(L) - 1)]
                ]

                length = lambda p0, p1: Point(p0).distance(Point(p1))
                seg_lens = [
                    length(pts[0], pts[1])
                    for pts in [L[index : index + 2] for index in range(len(L) - 1)]
                ]

                m = [ydiff / seglen for ydiff, seglen in zip(ydiffs, seg_lens)]
                l = [xdiff / seglen for xdiff, seglen in zip(xdiffs, seg_lens)]

                lcomb = lambda midx, midy, l, m: Point(midx + (10 * m), midy - (10 * l))
                rcomb = lambda midx, midy, l, m: Point(midx - (10 * m), midy + (10 * l))
                lgeomList += [
                    lcomb(x, y, l1, m1) for x, y, l1, m1 in zip(xmids, ymids, l, m)
                ]
                rgeomList += [
                    rcomb(x, y, l1, m1) for x, y, l1, m1 in zip(xmids, ymids, l, m)
                ]
                xmidsList += xmids
                ymidsList += ymids
                faultIds += [fault["GEOMETRY_OBJECT_ID"]] * len(xmids)

        # Create geometry from left and right points list and join with geology to
        # find which formation the point lands in
        lgdf = gpd.GeoDataFrame(crs=map_data.working_projection, geometry=lgeomList)
        rgdf = gpd.GeoDataFrame(crs=map_data.working_projection, geometry=rgeomList)
        lcode = gpd.sjoin(lgdf, local_geology, how="left", predicate="within")
        lcode = lcode[~lcode.index.duplicated(keep="first")]
        rcode = gpd.sjoin(rgdf, local_geology, how="left", predicate="within")
        rcode = rcode[~rcode.index.duplicated(keep="first")]

        # For each set of joined points fill a 2D list (data) with point information and
        # what formation is left and right of it, (also list strat column difference and
        # thus minimum throw for the fault at that position)
        for i in range(0, len(lcode)):
            if (
                not str(lcode.iloc[i]["UNIT_NAME"]) == "nan"
                and not str(rcode.iloc[i]["UNIT_NAME"]) == "nan"
            ):
                lcode_fm = lcode.iloc[i]["UNIT_NAME"]
                rcode_fm = rcode.iloc[i]["UNIT_NAME"]

                if lcode_fm in codes and rcode_fm in codes:
                    fm_l = int(new_als.loc[lcode_fm]["index"])
                    fm_r = int(new_als.loc[rcode_fm]["index"])

                    if fm_l > fm_r:
                        t = fm_l
                        fm_l = fm_r
                        fm_r = t
                    diff = fm_r - fm_l
                    number_string = str(diff)
                    diff = number_string.zfill(3)
                    if lcode_fm in formations and rcode_fm in formations:
                        min_offset = fm_thick_arr[fm_l, fm_r]
                    else:
                        min_offset = -1
                    data.append(
                        [
                            xmidsList[i],
                            ymidsList[i],
                            "Fault_" + str(faultIds[i]),
                            lcode_fm,
                            rcode_fm,
                            min_offset,
                            diff,
                        ]
                    )
                else:
                    data.append(
                        [
                            xmidsList[i],
                            ymidsList[i],
                            "Fault_" + str(faultIds[i]),
                            "",
                            "",
                            -1,
                            -1,
                        ]
                    )
    # Convert list to Dataframe and output to csv
    df = pd.DataFrame(data, columns=columns)
    df.to_csv(
        os.path.join(config.output_path, "fault_strat_offset3.csv"),
        index=False,
        columns=columns,
    )
    if config.verbose_level != VerboseLevel.NONE:
        print(
            "minimum stratigraphic offsets saved as",
            os.path.join(config.output_path, "fault_strat_offset3.csv"),
        )


##########################################################
# Extract cover thickness dip and contact info from depth to basement grid
# and/or vector cover shapefile
##########################################################


@beartype.beartype
def process_cover(
    config: Config,
    map_data: MapData,
    workflow: dict,
    use_vector: bool = True,
    use_grid: bool = True,
):
    if (
        use_grid and use_vector
    ):  # assumes a grid of depth to cover, with a defined null value for no cover, and a vector description of cover limits
        if config.verbose_level != VerboseLevel.NONE:
            print("use_vector, use_grid", use_vector, use_grid)

        bbox = config.bbox
        bbox3D = config.bbox_3d
        spacing = config.run_flags["cover_spacing"]
        nx = int((bbox[2] - bbox[0]) / spacing)
        ny = int((bbox[3] - bbox[1]) / spacing)
        x = np.linspace(bbox[0], bbox[2], nx)
        y = np.linspace(bbox[1], bbox[3], ny)
        xi, yi = np.meshgrid(x, y)
        xi, yi = xi.flatten(), yi.flatten()
        df = pd.DataFrame({"X": xi, "Y": yi})
        df["coords"] = list(zip(df["X"], df["Y"]))
        df["coords"] = df["coords"].apply(Point)
        df["cover"] = 1
        cover_pts = gpd.GeoDataFrame(df, geometry="coords")
        cover_pts.crs = map_data.working_projection

        cover = map_data.get_map_data(Datatype.COVER_MAP)
        cover_buffered = gpd.GeoDataFrame(
            geometry=map_data.get_map_data(Datatype.COVER_MAP).buffer(-1500)
        )

        actual_cover = gpd.sjoin(
            cover_pts, cover_buffered, how="inner", predicate="within"
        )
        actual_cover["index_right"] = actual_cover["index_right"].fillna(0)
        if config.verbose_level != VerboseLevel.NONE:
            print("df,actual_cover", len(df), len(actual_cover))
        allpts = open(os.path.join(config.output_path, "cover_grid.csv"), "w")
        allpts.write("X,Y,Z,formation\n")
        dtm = map_data.get_map_data(Datatype.DTM).open()
        for indx, pt in actual_cover.iterrows():
            locations = [(pt["X"], pt["Y"])]
            height = m2l_utils.value_from_dtm_dtb(
                dtm, map_data.dtb, map_data.dtb_null, workflow["cover_map"], locations
            )
            ostr = "{},{},{},{}\n".format(pt["X"], pt["Y"], height, "cover")
            allpts.write(ostr)
            if (
                np.fabs(pt["X"] - bbox3D["minx"]) > 1000
                and np.fabs(pt["X"] - bbox3D["maxx"]) > 1000
                and np.fabs(pt["Y"] - bbox3D["miny"]) > 1000
                and np.fabs(pt["Y"] - bbox3D["maxy"]) > 1000
            ):
                ostr = "{},{},{},{}\n".format(
                    pt["X"], pt["Y"], float(height) + 5000, "cover_up"
                )
                allpts.write(ostr)

        for indx, cpoly in map_data.get_map_data(Datatype.COVER_MAP).iterrows():
            # need to ignore points outside bbox and make poly os bbox
            coords = extract_poly_coords(cpoly.geometry, 0)
            k = 0
            for pt in coords["exterior_coords"]:
                # decimate to reduce number of points, but also take second and third point of a series
                if (
                    k % config.run_flags["contact_decimate"] == 0
                    or k == int((len(coords["exterior_coords"]) - 1) / 2)
                    or k == len(coords["exterior_coords"]) - 1
                ):
                    if (
                        pt[0] > bbox[0]
                        and pt[0] < bbox[2]
                        and pt[1] > bbox[1]
                        and pt[1] < bbox[3]
                    ):
                        locations = [(pt[0], pt[1])]

                        height = m2l_utils.value_from_dtm_dtb(
                            dtm, map_data.dtb, map_data.dtb_null, False, locations
                        )
                        ostr = "{},{},{},{}\n".format(pt[0], pt[1], height, "cover")
                        # ostr = str(pt[0])+","+str(pt[1])+","+height+",cover\n"
                        allpts.write(ostr)
                        if (
                            np.fabs(pt[0] - bbox3D["minx"]) > 1000
                            and np.fabs(pt[0] - bbox3D["maxx"]) > 1000
                            and np.fabs(pt[1] - bbox3D["miny"]) > 1000
                            and np.fabs(pt[1] - bbox3D["maxy"]) > 1000
                        ):
                            ostr = "{},{},{},{}\n".format(
                                pt[0], pt[1], bbox3D["top"] + 5000, "cover"
                            )
                            # ostr = str(pt[0])+","+str(pt[1])+","+height+",cover\n"
                            allpts.write(ostr)
                k = k + 1
            if len(coords["interior_coords"]) > 0:
                for i in range(0, len(coords["interior_coords"]), 2):
                    for pts in coords["interior_coords"][i + 1 : i + 2]:
                        for pt in pts:
                            # decimate to reduce number of points, but also take second and third point of a series
                            if (
                                k % config.run_flags["contact_decimate"] == 0
                                or k == int((len(coords["interior_coords"]) - 1) / 2)
                                or k == len(coords["interior_coords"]) - 1
                            ):
                                if (
                                    pt[0] > bbox[0]
                                    and pt[0] < bbox[2]
                                    and pt[1] > bbox[1]
                                    and pt[1] < bbox[3]
                                ):
                                    locations = [(pt[0], pt[1])]

                                    height = m2l_utils.value_from_dtm_dtb(
                                        dtm,
                                        map_data.dtb,
                                        map_data.dtb_null,
                                        False,
                                        locations,
                                    )
                                    ostr = "{},{},{},{}\n".format(
                                        pt[0], pt[1], height, "cover"
                                    )

                                    # ostr = str(pt[0])+","+str(pt[1])+","+height+",cover\n"
                                    allpts.write(ostr)
                                    ostr = "{},{},{},{}\n".format(
                                        pt[0], pt[1], bbox3D["top"] + 5000, "cover"
                                    )
                                    # ostr = str(pt[0])+","+str(pt[1])+","+height+",cover\n"
                                    allpts.write(ostr)
                k = k + 1

        allpts.close()
        if config.verbose_level != VerboseLevel.NONE:
            print(
                "cover grid saved out as",
                os.path.join(config.output_path, "cover_grid.csv"),
            )

    elif (
        use_grid and not use_vector
    ):  # assumes a grid of depth to cover, with a defined null value for no cover, but no vector description of cover limits
        if config.verbose_level != VerboseLevel.NONE:
            print("use_vector, use_grid", use_vector, use_grid)

        nx = int((bbox[2] - bbox[0]) / spacing)
        ny = int((bbox[3] - bbox[1]) / spacing)
        x = np.linspace(bbox[0], bbox[2], nx)
        y = np.linspace(bbox[1], bbox[3], ny)
        xi, yi = np.meshgrid(x, y)
        xi, yi = xi.flatten(), yi.flatten()
        df = pd.DataFrame({"X": xi, "Y": yi})
        df["coords"] = list(zip(df["X"], df["Y"]))
        df["coords"] = df["coords"].apply(Point)
        cover_pts = gpd.GeoDataFrame(df, geometry="coords")
        cover_pts.crs = map_data.working_projection

        allpts = open(os.path.join(config.output_path, "cover_grid.csv"), "w")
        allpts.write("X,Y,Z,formation\n")

        for indx, pt in cover_pts.iterrows():
            locations = [(pt["X"], pt["Y"])]
            height = m2l_utils.value_from_dtm_dtb(
                dtm, map_data.dtb, map_data.dtb_null, workflow["cover_map"], locations
            )
            ostr = "{},{},{},{}\n".format(pt["X"], pt["Y"], height, "cover")
            # ostr = str(pt['X'])+','+str(pt['Y'])+','+str(height)+',cover\n'
            allpts.write(ostr)
            ostr = "{},{},{},{}\n".format(
                pt["X"], pt["Y"], float(height) + 5000, "cover"
            )
            # ostr = str(pt['X'])+','+str(pt['Y'])+','+str(height)+',cover\n'
            # allpts.write(ostr)

        allpts.close()
        if config.verbose_level != VerboseLevel.NONE:
            print(
                "cover grid saved out as",
                os.path.join(config.output_path, "cover_grid.csv"),
            )

    if use_vector:  # assume vector of limits of cover
        allo = open(os.path.join(config.output_path, "cover_orientations.csv"), "w")
        allo.write("X,Y,Z,azimuth,dip,polarity,formation\n")

        for indx, cpoly in cover.iterrows():
            # need toignore points outside bbox and make poly os bbox

            coords = extract_poly_coords(cpoly.geometry, 0)
            k = 0
            first = True
            for pt in coords["exterior_coords"]:
                if first:
                    lastx = pt[0]
                    lasty = pt[1]
                    first = False
                # decimate to reduce number of points, but also take second and third point of a series
                locations = [(pt[0], pt[1])]
                if (
                    k % config.run_flags["contact_decimate"] == 0
                    or k == int((len(coords["exterior_coords"]) - 1) / 2)
                    or k == len(coords["exterior_coords"]) - 1
                ):
                    if (
                        pt[0] > bbox[0]
                        and pt[0] < bbox[2]
                        and pt[1] > bbox[1]
                        and pt[1] < bbox[3]
                    ):
                        dlsx = lastx - pt[0]
                        dlsy = lasty - pt[1]
                        lastx = pt[0]
                        lasty = pt[1]
                        if not dlsx + dlsy == 0.0:
                            lsx = dlsx / sqrt((dlsx * dlsx) + (dlsy * dlsy))
                            lsy = dlsy / sqrt((dlsx * dlsx) + (dlsy * dlsy))

                            locations = [(pt[0], pt[1])]
                            height = m2l_utils.value_from_dtm_dtb(
                                dtm,
                                map_data.dtb,
                                map_data.dtb_null,
                                workflow["cover_map"],
                                locations,
                            )
                            # normal to line segment
                            azimuth = (180 + degrees(atan2(lsy, -lsx))) % 360
                            # pt just a bit in/out from line
                            testpx = pt[0] - lsy
                            testpy = pt[1] + lsx

                            df = pd.DataFrame(
                                {"point": ["apoint"], "X": [testpx], "Y": [testpy]}
                            )
                            gdf = gpd.GeoDataFrame(
                                df, geometry=gpd.points_from_xy(df.X, df.Y)
                            )
                            gdf.crs = map_data.working_projection
                            point_within = gpd.sjoin(gdf, cover, predicate="within")
                            if len(point_within) > 0:
                                # if Polygon(cpoly.geometry).contains(Point(testpx, testpy)):
                                azimuth = (azimuth) % 360
                            else:
                                azimuth = (azimuth - 180) % 360
                            ostr = "{},{},{},{},{},{},{}\n".format(
                                pt[0],
                                pt[1],
                                height,
                                azimuth,
                                config.run_flags["cover_dip"],
                                "1",
                                "cover",
                            )
                            # ostr = str(pt[0])+","+str(pt[1])+","+str(height)+","+str(azimuth)+","+str(config.run_flags['cover_dip'])+",1,cover\n"
                            allo.write(ostr)
                            ostr = "{},{},{},{},{},{},{}\n".format(
                                pt[0],
                                pt[1],
                                float(height) + 5000,
                                azimuth,
                                config.run_flags["cover_dip"],
                                "1",
                                "cover_up",
                            )
                            # ostr = str(pt[0])+","+str(pt[1])+","+str(height)+","+str(azimuth)+","+str(config.run_flags['cover_dip'])+",1,cover\n"
                            # allo.write(ostr)

                k = k + 1
            first = True
            if len(coords["interior_coords"]) > 0:
                for i in range(0, len(coords["interior_coords"]), 2):
                    for pts in coords["interior_coords"][i + 1 : i + 2]:
                        for pt in pts:
                            if first:
                                lastx = pt[0]
                                lasty = pt[1]
                                first = False
                            # decimate to reduce number of points, but also take second and third point of a series
                            locations = [(pt[0], pt[1])]
                            if (
                                k % config.run_flags["contact_decimate"] == 0
                                or k == int((len(coords["interior_coords"]) - 1) / 2)
                                or k == len(coords["interior_coords"]) - 1
                            ):
                                if (
                                    pt[0] > bbox[0]
                                    and pt[0] < bbox[2]
                                    and pt[1] > bbox[1]
                                    and pt[1] < bbox[3]
                                ):
                                    dlsx = lastx - pt[0]
                                    dlsy = lasty - pt[1]
                                    lastx = pt[0]
                                    lasty = pt[1]
                                    if not dlsx + dlsy == 0.0:
                                        lsx = dlsx / sqrt((dlsx * dlsx) + (dlsy * dlsy))
                                        lsy = dlsy / sqrt((dlsx * dlsx) + (dlsy * dlsy))

                                        locations = [(pt[0], pt[1])]
                                        height = m2l_utils.value_from_dtm_dtb(
                                            dtm,
                                            map_data.dtb,
                                            map_data.dtb_null,
                                            workflow["cover_map"],
                                            locations,
                                        )
                                        # normal to line segment
                                        azimuth = (
                                            180 + degrees(atan2(lsy, -lsx))
                                        ) % 360
                                        # pt just a bit in/out from line
                                        testpx = pt[0] - lsy
                                        testpy = pt[1] + lsx
                                        df = pd.DataFrame(
                                            {
                                                "point": ["apoint"],
                                                "X": [testpx],
                                                "Y": [testpy],
                                            }
                                        )
                                        gdf = gpd.GeoDataFrame(
                                            df, geometry=gpd.points_from_xy(df.X, df.Y)
                                        )
                                        gdf.crs = map_data.working_projection
                                        point_within = gpd.sjoin(
                                            gdf, cover, predicate="within"
                                        )
                                        if len(point_within) > 0:
                                            # if Polygon(cpoly.geometry).contains(Point(testpx, testpy)):
                                            azimuth = (azimuth) % 360
                                        else:
                                            azimuth = (azimuth - 180) % 360
                                        ostr = "{},{},{},{},{},{},{}\n".format(
                                            pt[0],
                                            pt[1],
                                            height,
                                            azimuth,
                                            config.run_flags["cover_dip"],
                                            "1",
                                            "cover",
                                        )

                                        # ostr = str(pt[0])+","+str(pt[1])+","+str(height)+","+str(azimuth)+","+str(config.run_flags['cover_dip'])+",1,cover\n"
                                        allo.write(ostr)
                                        ostr = "{},{},{},{},{},{},{}\n".format(
                                            pt[0],
                                            pt[1],
                                            float(height) + 5000,
                                            azimuth,
                                            config.run_flags["cover_dip"],
                                            "1",
                                            "cover_up",
                                        )

                                        # ostr = str(pt[0])+","+str(pt[1])+","+str(height)+","+str(azimuth)+","+str(config.run_flags['cover_dip'])+",1,cover\n"
                                        # allo.write(ostr)

                            k = k + 1
    elif use_grid and not use_vector:  # assumes grid but no vector of limits of cover
        allo = open(os.path.join(config.output_path, "cover_orientations.csv"), "w")
        allo.write("X,Y,Z,azimuth,dip,polarity,formation\n")
        midx = bbox[0] + ((bbox[2] - bbox[0]) / 2)
        midy = bbox[1] + ((bbox[3] - bbox[1]) / 2)
        ostr = "{},{},{},{},{},{},{}\n".format(midx, midy, "0", "0", "0", "1", "cover")
        # ostr = str(midx)+","+str(midy)+","+str(0)+","+str(0)+","+str(0)+",1,cover\n"
        allo.write(ostr)

        allo.close()
        if config.verbose_level != VerboseLevel.NONE:
            print(
                "cover orientations saved out as",
                os.path.join(config.output_path, "cover_orientations.csv"),
            )


##########################################################
# Save out dip info along basal contacts, dip defined, dip direction normal to local vector
##########################################################
@beartype.beartype
def save_basal_contacts_orientations_csv(
    config: Config, map_data: MapData, workflow: dict
):
    height_above_offset = 1000.0
    depth_below_offset = 1000.0

    # interpolated_combo_file = os.path.join(config.tmp_path, 'combo_full.csv')
    # orientations = pd.read_csv(interpolated_combo_file)
    fp = open(os.path.join(config.output_path, "contact_projections.csv"), "w")
    fp.write("X,Y,Z,formation\n")

    f = open(os.path.join(config.output_path, "contact_orientations.csv"), "w")
    f.write("X,Y,Z,azimuth,dip,polarity,formation\n")
    contacts = map_data.basal_contacts_no_faults
    first_geom = contacts.iloc[0].geometry
    dtm = map_data.get_map_data(Datatype.DTM).open()
    for index, contact in contacts[:-1].iterrows():
        i = 0
        # print(contact['UNIT_NAME'])
        first = True
        if contact.geometry is not None and contact.geometry != first_geom:
            if contact.geometry.type == "MultiLineString":  # why not LineString?
                for line in contact.geometry.geoms:
                    # first_in_line = True
                    if i % config.run_flags["contact_decimate"] == 0:
                        if first:
                            lastx = line.coords[0][0]
                            lasty = line.coords[0][1]
                            first = False
                        else:
                            l, m = m2l_utils.pts2dircos(
                                lastx, lasty, line.coords[0][0], line.coords[0][1]
                            )
                            midx = lastx + ((line.coords[0][0] - lastx) / 2)
                            midy = lasty + ((line.coords[0][1] - lasty) / 2)

                            dip, dipdir = m2l_utils.dircos2ddd(-m, l, 0)

                            r = int(
                                (midy - config.bbox[1])
                                / config.run_flags["interpolation_spacing"]
                            )
                            c = int(
                                (midx - config.bbox[0])
                                / config.run_flags["interpolation_spacing"]
                            )
                            if map_data.polarity_grid[r, c] < 0:
                                dipdir = fmod(dipdir + 180, 360)
                                polarity = 0
                            else:
                                polarity = 1

                            locations = [(midx, midy)]

                            height = m2l_utils.value_from_dtm_dtb(
                                dtm,
                                map_data.dtb,
                                map_data.dtb_null,
                                workflow["cover_map"],
                                locations,
                            )

                            if config.run_flags["contact_dip"] == -999:
                                dip = map_data.dip_grid[r, c]
                                if not dip == -999:
                                    if dip > 90:
                                        dip = 180 - dip
                                        flip = True
                                    else:
                                        flip = False
                                    locations1 = [(lastx, lasty)]
                                    height1 = m2l_utils.value_from_dtm_dtb(
                                        dtm,
                                        map_data.dtb,
                                        map_data.dtb_null,
                                        workflow["cover_map"],
                                        locations1,
                                    )
                                    locations2 = [
                                        (line.coords[0][0], line.coords[0][1])
                                    ]
                                    height2 = m2l_utils.value_from_dtm_dtb(
                                        dtm,
                                        map_data.dtb,
                                        map_data.dtb_null,
                                        workflow["cover_map"],
                                        locations2,
                                    )

                                    l1, m1, n1, l2, m2, n2 = lmn_from_line_dip(
                                        lastx,
                                        lasty,
                                        height1,
                                        line.coords[0][0],
                                        line.coords[0][1],
                                        height2,
                                        dip,
                                    )

                                    if (
                                        (not l1 == -999)
                                        and m * l1 - l * m1 < 1
                                        and m * l1 - l * m1 > -1
                                        and m * l2 - l * m2 < 1
                                        and m * l2 - l * m2 > -1
                                    ):
                                        if polarity == 0:
                                            dotproduct1 = acos(m * l1 - l * m1)
                                            dotproduct2 = acos(m * l2 - l * m2)
                                        else:
                                            dotproduct1 = acos(-(m * l1 - l * m1))
                                            dotproduct2 = acos(-(m * l2 - l * m2))

                                        if dotproduct1 < dotproduct2:
                                            dip = 90 - degrees(asin(n1))
                                            lc = l1 / sqrt(l1**2 + m1**2)
                                            mc = m1 / sqrt(l1**2 + m1**2)
                                        else:
                                            dip = 90 - degrees(asin(n2))
                                            lc = l2 / sqrt(l2**2 + m2**2)
                                            mc = m2 / sqrt(l2**2 + m2**2)

                                        d, dipdir = m2l_utils.dircos2ddd(lc, mc, 0)
                                        if flip:
                                            dipdir = (dipdir + 180) % 360

                                        if dip > 90:
                                            dip = 180 - dip
                                        # print("orig_fdip=",map_data.dip_grid[r, c], "new_dips=",dip,90-degrees(asin(n1)),90-degrees(asin(n2)))
                                    else:
                                        dip = map_data.dip_grid[r, c]
                                else:
                                    dip = 90

                            else:
                                dip = config.run_flags["contact_dip"]
                            gap = m2l_utils.ptsdist(
                                lastx, lasty, line.coords[0][0], line.coords[0][1]
                            )
                            if dip != -999 and gap < 2000:
                                ostr = "{},{},{},{},{},{},{}\n".format(
                                    midx,
                                    midy,
                                    height,
                                    dipdir,
                                    str(dip),
                                    polarity,
                                    str(contact["UNIT_NAME"])
                                    .replace(" ", "_")
                                    .replace("-", "_"),
                                )
                                # ostr = str(midx)+','+str(midy)+','+str(height)+','+str(dipdir)+','+str(config.run_flags['contact_dip'])+',1,'+str(contact['UNIT_NAME']).replace(" ","_").replace("-","_")+'\n'
                                f.write(ostr)

                                l, m, n = m2l_utils.ddd2dircos(90.0 - dip, dipdir)
                                ostr = "{},{},{},{}\n".format(
                                    midx - (l * height_above_offset),
                                    midy - (m * height_above_offset),
                                    float(height) + (n * height_above_offset),
                                    contact["UNIT_NAME"],
                                )
                                fp.write(ostr)

                                ostr = "{},{},{},{}\n".format(
                                    midx + (l * depth_below_offset),
                                    midy + (m * depth_below_offset),
                                    float(height) - (n * depth_below_offset),
                                    contact["UNIT_NAME"],
                                )
                                fp.write(ostr)
                            lastx = line.coords[0][0]
                            lasty = line.coords[0][1]

                    else:
                        lastx = line.coords[0][0]
                        lasty = line.coords[0][1]

                    i = i + 1
            else:
                if config.verbose_level != VerboseLevel.NONE:
                    print("other basal contact geom ignored", contact.geometry.type)
    f.close()
    fp.close()


def process_sills(
    output_path,
    geol_clip,
    dtm,
    dtb,
    dtb_null,
    cover_map,
    contact_decimate,
    c_l,
    dip_grid,
    x,
    y,
    spacing,
    bbox,
    buffer,
):
    sills = geol_clip[geol_clip["DESCRIPTION"].str.contains(c_l["sill"])]
    sills = sills[sills["ROCKTYPE1"].str.contains(c_l["intrusive"])]

    sill_dict = {}
    i = 0
    for ind, sill in sills.iterrows():
        for ind2, geol in geol_clip.iterrows():
            if geol["GEOMETRY_OBJECT_ID"] != sill["GEOMETRY_OBJECT_ID"]:
                if geol.geometry.intersects(sill.geometry):
                    LineStringC = geol.geometry.intersection(sill.geometry)
                    if (
                        LineStringC.wkt.split(" ")[0] == "MULTIPOLYGON"
                        or LineStringC.wkt.split(" ")[0] == "POLYGON"
                    ):  # ignore polygon intersections for now, worry about them later!
                        print(
                            geol["GEOMETRY_OBJECT_ID"],
                            "debug:",
                            LineStringC.geometry.type,
                        )
                        continue

                    elif (
                        LineStringC.wkt.split(" ")[0] == "MULTILINESTRING"
                        or LineStringC.wkt.split(" ")[0] == "GEOMETRYCOLLECTION"
                    ):
                        k = 0
                        for lineC in LineStringC:  # process all linestrings
                            # first = True
                            if lineC.wkt.split(" ")[0] == "LINESTRING":
                                # decimate to reduce number of points, but also take second and third point of a series to keep gempy happy
                                if (
                                    k % contact_decimate == 0
                                    or k == int((len(LineStringC) - 1) / 2)
                                    or k == len(LineStringC) - 1
                                ):
                                    # doesn't like point right on edge?

                                    locations = [
                                        (lineC.coords[0][0], lineC.coords[0][1])
                                    ]
                                    if (
                                        lineC.coords[0][0] > dtm.bounds[0]
                                        and lineC.coords[0][0] < dtm.bounds[2]
                                        and lineC.coords[0][1] > dtm.bounds[1]
                                        and lineC.coords[0][1] < dtm.bounds[3]
                                    ):
                                        height = m2l_utils.value_from_dtm_dtb(
                                            dtm, dtb, dtb_null, cover_map, locations
                                        )

                                        dlsx = lineC.coords[0][0] - lineC.coords[1][0]
                                        dlsy = lineC.coords[0][1] - lineC.coords[1][1]
                                        lsx = dlsx / sqrt((dlsx * dlsx) + (dlsy * dlsy))
                                        lsy = dlsy / sqrt((dlsx * dlsx) + (dlsy * dlsy))

                                        azimuth = (
                                            180 + degrees(atan2(lsy, -lsx))
                                        ) % 360

                                        # pt just a bit in/out from line
                                        testpx = lineC.coords[0][0] - lsy
                                        testpy = lineC.coords[0][0] + lsx

                                        midx = lineC.coords[0][0] + (
                                            (lineC.coords[1][0] - lineC.coords[0][0])
                                            / 2
                                        )
                                        midy = lineC.coords[0][1] + (
                                            (lineC.coords[1][1] - lineC.coords[0][1])
                                            / 2
                                        )
                                        # midpoint = Point(midx, midy)
                                        dx1 = -lsy * buffer
                                        dy1 = lsx * buffer
                                        dx2 = -dx1
                                        dy2 = -dy1

                                        if sill.geometry.type == "Polygon":
                                            if Polygon(sill.geometry).contains(
                                                Point(testpx, testpy)
                                            ):
                                                azimuth = (azimuth - 180) % 360
                                        else:
                                            if MultiPolygon(sill.geometry).contains(
                                                Point(testpx, testpy)
                                            ):
                                                azimuth = (azimuth - 180) % 360

                                        p1 = Point(midx + lsy, midy - lsx)
                                        p2 = Point((midx + dx2, midy + dy2))

                                        r = int((midy - bbox[1]) / spacing)
                                        c = int((midx - bbox[0]) / spacing)

                                        dip_mean = dip_grid[r, c]
                                        ddline = LineString((p1, p2))
                                        # print(ddline,midpoint)
                                        if ddline.intersects(sill.geometry):
                                            isects = ddline.intersection(sill.geometry)
                                            if isects.geom_type == "MultiLineString":
                                                min_dist = 1e9
                                                for line in isects:
                                                    app_thickness = m2l_utils.ptsdist(
                                                        line.coords[1][0],
                                                        line.coords[1][1],
                                                        midx,
                                                        midy,
                                                    )
                                                    if app_thickness < buffer * 2:
                                                        if min_dist > app_thickness:
                                                            min_dist = app_thickness
                                                app_thickness = min_dist
                                                est_thickness = app_thickness * sin(
                                                    radians(dip_mean)
                                                )

                                            else:
                                                # print(isects)
                                                app_thickness = m2l_utils.ptsdist(
                                                    isects.coords[1][0],
                                                    isects.coords[1][1],
                                                    midx,
                                                    midy,
                                                )
                                                if app_thickness < buffer * 2:
                                                    est_thickness = app_thickness * sin(
                                                        radians(dip_mean)
                                                    )
                                        else:
                                            app_thickness = -999
                                            est_thickness = -999

                                        sill_dict[i] = {
                                            "X": lineC.coords[0][0],
                                            "Y": lineC.coords[0][1],
                                            "Z": height,
                                            "sill_code": sill["UNIT_NAME"],
                                            "host_code": geol["UNIT_NAME"],
                                            "outwards": azimuth,
                                            "apparent thickness": app_thickness,
                                            "true thickness": est_thickness,
                                        }
                                        i = i + 1
                                    else:
                                        continue

                                k += 1

    sills_df = pd.DataFrame.from_dict(sill_dict, orient="index")
    sills_df.to_csv(os.path.join(output_path, "sills.csv"))


def combine_point_data(output_path, tmp_path):
    Aorientations = pd.read_csv(
        os.path.join(output_path, "orientations_clean.csv"), sep=","
    )
    d = {
        "formation": "name",
        "azimuth": "Param1",
        "dip": "Param2",
        "polarity": "Param3",
    }
    Aorientations.rename(columns=d, inplace=True)
    Aorientations["type"] = "orientation"
    Aorientations["Param4"] = None
    Aorientations = Aorientations[
        [
            "source",
            "type",
            "name",
            "X",
            "Y",
            "Z",
            "Param1",
            "Param2",
            "Param3",
            "Param4",
        ]
    ]
    all_points = Aorientations.copy()

    if os.path.isfile(os.path.join(output_path, "faults.csv")):
        Afaults = pd.read_csv(os.path.join(output_path, "faults.csv"), sep=",")
        d = {"formation": "name"}
        Afaults.rename(columns=d, inplace=True)
        Afaults["type"] = "fault_geom"
        Afaults["Param1"] = None
        Afaults["Param2"] = None
        Afaults["Param3"] = None
        Afaults["Param4"] = None
        Afaults["source"] = "calc"
        Afaults = Afaults[
            [
                "source",
                "type",
                "name",
                "X",
                "Y",
                "Z",
                "Param1",
                "Param2",
                "Param3",
                "Param4",
            ]
        ]
        all_points = pd.concat([all_points, Afaults])

    if os.path.isfile(os.path.join(output_path, "fault_displacements3.csv")):
        Afault_displacements = pd.read_csv(
            os.path.join(output_path, "fault_displacements3.csv"), sep=","
        )
        d = {
            "fname": "name",
            "apparent_displacement": "Param1",
            "vertical_displacement": "Param2",
            "downthrow_dir": "Param3",
        }
        Afault_displacements.rename(columns=d, inplace=True)
        Afault_displacements["type"] = "fault_displacement"
        Afault_displacements["Param4"] = None
        Afault_displacements["Z"] = None
        Afault_displacements["source"] = "calc"
        Afault_displacements = Afault_displacements[
            [
                "source",
                "type",
                "name",
                "X",
                "Y",
                "Z",
                "Param1",
                "Param2",
                "Param3",
                "Param4",
            ]
        ]
        all_points = pd.concat([all_points, Afault_displacements])

    if os.path.isfile(os.path.join(output_path, "fault_strat_offset3.csv")):
        Afaults_strat_displacements = pd.read_csv(
            os.path.join(output_path, "fault_strat_offset3.csv"), sep=","
        )
        d = {
            "id": "name",
            "left_fm": "Param1",
            "right_fm": "Param2",
            "min_offset": "Param3",
            "strat_offset": "Param4",
        }
        Afaults_strat_displacements.rename(columns=d, inplace=True)
        Afaults_strat_displacements["type"] = "fault_strat_displacement"
        Afaults_strat_displacements["Z"] = None
        Afaults_strat_displacements["source"] = "calc"
        Afaults_strat_displacements = Afaults_strat_displacements[
            [
                "source",
                "type",
                "name",
                "X",
                "Y",
                "Z",
                "Param1",
                "Param2",
                "Param3",
                "Param4",
            ]
        ]
        all_points = pd.concat([all_points, Afaults_strat_displacements])

    if os.path.isfile(os.path.join(output_path, "contacts_clean.csv")):
        Acontacts = pd.read_csv(
            os.path.join(output_path, "contacts_clean.csv"), sep=","
        )
        d = {"formation": "name"}
        Acontacts.drop(labels="index", axis=1, inplace=True)
        Acontacts.rename(columns=d, inplace=True)
        Acontacts["type"] = "contact"
        Acontacts["Param1"] = None
        Acontacts["Param2"] = None
        Acontacts["Param3"] = None
        Acontacts["Param4"] = None
        Acontacts = Acontacts[
            [
                "source",
                "type",
                "name",
                "X",
                "Y",
                "Z",
                "Param1",
                "Param2",
                "Param3",
                "Param4",
            ]
        ]
        all_points = pd.concat([all_points, Acontacts])

    if os.path.exists(os.path.join(output_path, "secondary_orientations.csv")):
        Asecondaryorientations = pd.read_csv(
            os.path.join(output_path, "secondary_orientations.csv"), sep=","
        )
        d = {
            "formation": "name",
            "azimuth": "Param1",
            "dip": "Param2",
            "polarity": "Param3",
        }
        Asecondaryorientations.rename(columns=d, inplace=True)
        Asecondaryorientations["type"] = "orientation"
        Asecondaryorientations["Param4"] = None
        Asecondaryorientations["source"] = "secondary_orientation"
        Asecondaryorientations = Asecondaryorientations[
            [
                "source",
                "type",
                "name",
                "X",
                "Y",
                "Z",
                "Param1",
                "Param2",
                "Param3",
                "Param4",
            ]
        ]
        all_points = pd.concat([all_points, Asecondaryorientations])

    if os.path.isfile(os.path.join(output_path, "raw_contacts.csv")):
        Araw_contacts = pd.read_csv(os.path.join(tmp_path, "raw_contacts.csv"), sep=",")
        d = {
            "formation": "name",
            "group": "Param1",
            "angle": "Param2",
            "lsx": "Param3",
            "lsy": "Param4",
        }
        Araw_contacts.rename(columns=d, inplace=True)
        Araw_contacts["type"] = "raw_contact"
        Araw_contacts["source"] = "raw_contact"
        Araw_contacts = Araw_contacts[
            [
                "source",
                "type",
                "name",
                "X",
                "Y",
                "Z",
                "Param1",
                "Param2",
                "Param3",
                "Param4",
            ]
        ]
        all_points = pd.concat([all_points, Araw_contacts])

    point_data = all_points.fillna(-99)
    point_data = point_data.to_dict("records")

    return point_data


def fault_filter(output_path, filter, cutoff, relationship, median_cutoff):
    Gloop = nx.read_gml(os.path.join(output_path, "loop.gml"))

    if filter == "StratOffset":
        points = Gloop.nodes["Point_data"]
        points_df = pd.DataFrame.from_dict(points["data"])
        Afaults_strat_displacements = points_df[
            points_df["type"] == "fault_strat_displacement"
        ]
        # Afaults_strat_displacements = Afaults_strat_displacements.set_index(
        # 'name')

        faults = [n for n, v in Gloop.nodes(data=True) if v["ntype"] == "fault"]

        median_offset = []
        fault_list = []
        for fault in faults:
            strat_offset = []
            for ind2, f in Afaults_strat_displacements.iterrows():
                if fault == ind2:
                    strat_offset.append(f["Param4"])
            fault_list.append(fault)
            median_offset.append(statistics.mean(strat_offset))
        median = statistics.median(median_offset)
        nodes_ignore = []
        nodes_use = []

        for f in range(0, len(fault_list)):
            if median_offset[f] < median:
                nodes_ignore.append(fault_list[f])
            else:
                nodes_use.append(fault_list[f])

    else:
        nodes_all = []
        if median_cutoff:
            for v in Gloop.nodes():
                if Gloop.nodes[v]["ntype"] == "fault":
                    nodes_all.append(Gloop.nodes[v][filter])

            cutoff = statistics.median(nodes_all)

        nodes_ignore = []
        nodes_use = []
        for v in Gloop.nodes():
            if relationship == "le":
                if (
                    Gloop.nodes[v]["ntype"] == "fault"
                    and Gloop.nodes[v][filter] <= cutoff
                ):
                    nodes_ignore.append(v)
                elif Gloop.nodes[v]["ntype"] == "fault":
                    nodes_use.append(v)
            else:
                if (
                    Gloop.nodes[v]["ntype"] == "fault"
                    and Gloop.nodes[v][filter] > cutoff
                ):
                    nodes_ignore.append(v)
                elif Gloop.nodes[v]["ntype"] == "fault":
                    nodes_use.append(v)

    return nodes_ignore


def lmn_from_line_dip(x1, y1, z1, x2, y2, z2, dip):
    """[Calculate direction cosines of a plane defined by a 3D line defined by the local contact orientationa and a known dip]
       [returns direction cosines of 2 possible planes or -999s if no solution possible]

    Args:
        x1 ([float]): [x position of start of contact 3D line segment]
        y1 ([float]): [y position of start of contact 3D line segment]
        z1 ([float]): [z position of start of contact 3D line segment]
        x2 ([float]): [x position of start of contact 3D line segment]
        y2 ([float]): [y position of start of contact 3D line segment]
        z2 ([float]): [z position of start of contact 3D line segment]
        dip ([float]): [estimated dip of plane]
    Returns:
        l1 ([float]): [solution 1 of l direction cosine of plane that contains 3D line segment and has a dip of dip with horizontal]
        m1 ([float]): [solution 1 of m direction cosine of plane that contains 3D line segment and has a dip of dip with horizontal]
        n1 ([float]): [solution 1 of n direction cosine of plane that contains 3D line segment and has a dip of dip with horizontal]
        l2 ([float]): [solution 2 of l direction cosine of plane that contains 3D line segment and has a dip of dip with horizontal]
        m2 ([float]): [solution 2 of m direction cosine of plane that contains 3D line segment and has a dip of dip with horizontal]
        n2 ([float]): [solution 2 of n direction cosine of plane that contains 3D line segment and has a dip of dip with horizontal]
    """
    x1 = float(x1)
    y1 = float(y1)
    z1 = float(z1)
    x2 = float(x2)
    y2 = float(y2)
    z2 = float(z2)

    dip_orig = dip
    C = cos(radians(dip))
    Z1 = -99
    while Z1 == -99 and dip < 91:
        try:
            Z1 = (
                C**2
                * (
                    -(
                        -2 * x1**2 * z2
                        + 2 * x1 * x2 * z1
                        + 2 * x1 * x2 * z2
                        - 2 * x2**2 * z1
                        - 2 * y1**2 * z2
                        + 2 * y1 * y2 * z1
                        + 2 * y1 * y2 * z2
                        - 2 * y2**2 * z1
                    )
                )
                - sqrt(
                    C**4.0
                    * (
                        -2 * x1**2 * z2
                        + 2 * x1 * x2 * z1
                        + 2 * x1 * x2 * z2
                        - 2 * x2**2 * z1
                        - 2 * y1**2 * z2
                        + 2 * y1 * y2 * z1
                        + 2 * y1 * y2 * z2
                        - 2 * y2**2 * z1
                    )
                    ** 2
                    - 4
                    * C**2
                    * (
                        x1**2
                        - 2 * x1 * x2
                        + x2**2
                        + y1**2
                        - 2 * y1 * y2
                        + y2**2
                    )
                    * (
                        C**2 * abs(x2 * y1 - x1 * y2) ** 2
                        + C**2 * x1**2 * z2**2
                        - 2 * C**2 * x1 * x2 * z1 * z2
                        + C**2 * x2**2 * z1**2
                        + C**2 * y1**2 * z2**2
                        - 2 * C**2 * y1 * y2 * z1 * z2
                        + C**2 * y2**2 * z1**2
                        - x1**2 * y2**2
                        + 2 * x1 * x2 * y1 * y2
                        - x2**2 * y1**2
                    )
                )
            ) / (
                2
                * C**2
                * (x1**2 - 2 * x1 * x2 + x2**2 + y1**2 - 2 * y1 * y2 + y2**2)
            )
        except Exception:
            dip = dip + 1
            C = cos(radians(dip))
    if Z1 == -99:
        print("no solution", x1, y1, z1, x2, y2, z2, dip_orig)
        return (-999, -999, -999, -999, -999, -999)

    C = cos(radians(dip))
    Z2 = -99
    while Z2 == -99 and dip < 91:
        try:
            Z2 = (
                sqrt(
                    C**4.0
                    * (
                        -2 * x1**2 * z2
                        + 2 * x1 * x2 * z1
                        + 2 * x1 * x2 * z2
                        - 2 * x2**2 * z1
                        - 2 * y1**2 * z2
                        + 2 * y1 * y2 * z1
                        + 2 * y1 * y2 * z2
                        - 2 * y2**2 * z1
                    )
                    ** 2
                    - 4
                    * C**2
                    * (
                        x1**2
                        - 2 * x1 * x2
                        + x2**2
                        + y1**2
                        - 2 * y1 * y2
                        + y2**2
                    )
                    * (
                        C**2 * abs(x2 * y1 - x1 * y2) ** 2
                        + C**2 * x1**2 * z2**2
                        - 2 * C**2 * x1 * x2 * z1 * z2
                        + C**2 * x2**2 * z1**2
                        + C**2 * y1**2 * z2**2
                        - 2 * C**2 * y1 * y2 * z1 * z2
                        + C**2 * y2**2 * z1**2
                        - x1**2 * y2**2
                        + 2 * x1 * x2 * y1 * y2
                        - x2**2 * y1**2
                    )
                )
                - C**2
                * (
                    -2 * x1**2 * z2
                    + 2 * x1 * x2 * z1
                    + 2 * x1 * x2 * z2
                    - 2 * x2**2 * z1
                    - 2 * y1**2 * z2
                    + 2 * y1 * y2 * z1
                    + 2 * y1 * y2 * z2
                    - 2 * y2**2 * z1
                )
            ) / (
                2
                * C**2
                * (x1**2 - 2 * x1 * x2 + x2**2 + y1**2 - 2 * y1 * y2 + y2**2)
            )
        except Exception:
            dip = dip + 1
            C = cos(radians(dip))
    if Z2 == -99:
        print("no solution", x1, y1, z1, x2, y2, z2, dip_orig)
        return (-999, -999, -999, -999, -999, -999)

    vector1 = [x2 - x1, y2 - y1, z2 - z1]
    vector2 = [0 - x1, 0 - y1, Z1 - z1]
    cross_product = [
        vector1[1] * vector2[2] - vector1[2] * vector2[1],
        -1 * vector1[0] * vector2[2] - vector1[2] * vector2[0],
        vector1[0] * vector2[1] - vector1[1] * vector2[0],
    ]
    d = cross_product[0] * x1 - cross_product[1] * y1 + cross_product[2] * z1

    a = cross_product[0]
    b = cross_product[1]
    c = cross_product[2]
    d = d
    l1, m1, n1 = (
        a / sqrt(a**2 + b**2 + c**2),
        b / sqrt(a**2 + b**2 + c**2),
        c / sqrt(a**2 + b**2 + c**2),
    )

    vector1 = [x2 - x1, y2 - y1, z2 - z1]
    vector2 = [0 - x1, 0 - y1, Z2 - z1]
    cross_product = [
        vector1[1] * vector2[2] - vector1[2] * vector2[1],
        -1 * vector1[0] * vector2[2] - vector1[2] * vector2[0],
        vector1[0] * vector2[1] - vector1[1] * vector2[0],
    ]
    d = cross_product[0] * x1 - cross_product[1] * y1 + cross_product[2] * z1

    a = cross_product[0]
    b = cross_product[1]
    c = cross_product[2]
    d = d
    l2 = a / sqrt(a**2 + b**2 + c**2)
    m2 = b / sqrt(a**2 + b**2 + c**2)
    n2 = c / sqrt(a**2 + b**2 + c**2)
    if l2 > 1:
        l2 = 1
    if m2 > 1:
        m2 = 1
    if n2 > 1:
        n2 = 1

    return (l1, m1, n1, l2, m2, n2)


@beartype.beartype
def update_fault_layer(config: Config, map_data: MapData):
    local_faults = map_data.get_map_data(Datatype.FAULT).copy()
    local_faults["name"] = local_faults["GEOMETRY_OBJECT_ID"].apply(
        lambda id: "Fault_" + str(id)
    )
    # display(local_faults)
    Gloop = nx.read_gml(config.output_path + "/loop.gml")
    fnodes_all = []
    for v in Gloop.nodes():
        if Gloop.nodes[v]["ntype"] == "fault":
            fnodes_all.append(v)
    fault_nodes = Gloop.subgraph(fnodes_all)
    fault_data = pd.DataFrame.from_dict(
        dict(fault_nodes.nodes(data=True)), orient="index"
    )
    fault_data["name"] = fault_data.index
    columns = {
        "ntype": "ntype",
        "Xmean": "Xmean",
        "Ymean": "Ymean",
        "Zmean": "Zmean",
        "HorizontalRadius": "HzRad",
        "VerticalRadius": "Vrad",
        "InfluenceDistance": "NDist",
        "IncLength": "IncLength",
        "f_colour": "colour",
        "Dip": "Dip_1",
        "DipDirection": "DipDir",
        "DipPolarity": "Polarity",
        "OrientationCluster": "OCluster",
        "LengthCluster": "LCluster",
        "ClosenessCentrality": "CCentral",
        "BetweennessCentrality": "BCentral",
    }
    fault_data = fault_data.rename(columns=columns, inplace=False)
    new_faults = local_faults.merge(fault_data, on="name")
    new_faults.crs = local_faults.crs
    # if len(new_faults) > 0:
    #     new_faults.to_file(config.tmp_path + "/faults_clip_data.shp")


@beartype.beartype
def save_interpolation_parameters(config: Config):
    Afaults = pd.read_csv(
        os.path.join(config.output_path, "fault_dimensions.csv"), sep=","
    )
    Astrat = pd.read_csv(os.path.join(config.tmp_path, "all_sorts_clean.csv"), sep=",")
    Astrat.drop_duplicates(subset="group", inplace=True)
    # Astrat.set_index('group',inplace=True)
    object_ip = {}
    index = 0
    for f in Afaults["Fault"]:
        object_ip[index] = {
            "objectname": f,
            "objecttype": "fault",
            "interpolatortype": "PLI",
            "nelements": 1e5,
            "regularisation": "0.1,0.1,0.1",
            "step": 10,
            "fault_buffer": 0.3,
            "solver": "cg",
            "cpw": 10,
            "npw": 10,
        }
        index = index + 1

    sgi = 0
    supergroups = {}
    with open(os.path.join(config.tmp_path, "super_groups.csv")) as sgf:
        lines = sgf.readlines()
        for l in lines:
            for g in l.split(","):
                g = g.replace("-", "_").replace(" ", "_").rstrip()
                if g:
                    supergroups[sgi] = g

            sgi += 1

    for s in supergroups:
        if supergroups[s] in Astrat.index:
            object_ip[index] = {
                "objectname": "supergroup_" + str(s),
                "objecttype": Astrat.loc[supergroups[s]]["strat_type"],
                "interpolatortype": "PLI",
                "nelements": 1e5,
                "regularisation": "0.1",
                "buffer": 1.8,
                "solver": "cg",
                "cpw": 10,
                "npw": 10,
            }
        index = index + 1

    object_ip_df = pd.DataFrame.from_dict(object_ip, orient="index")
    object_ip_df.to_csv(os.path.join(config.output_path, "object_ip.csv"), index=None)


def densify(geom, spacing):
    wkt = geom.wkt  # Get wkt
    geom = ogr.CreateGeometryFromWkt(wkt)
    # Modify the geometry such it has no segment longer than the given (maximum) length.
    geom.Segmentize(spacing)
    wkt2 = geom.ExportToWkt()
    new = loads(wkt2)
    return new
