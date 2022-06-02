import numpy as np
import pandas as pd

from ._geometry import points, linestrings, polygons, _simple_ix


class Frame:
    def to_dataframe(self, query, ids, tags, rels, ways=None):
        """Convert query results to a dataframe"""

        cols = ["osmid", "osmtype"]
        if query.metadata:
            cols = cols + ["changeset", "timestamp", "version"]
        df = pd.DataFrame(data=ids[:, 0 : len(cols) + 1], columns=cols)

        # convert tags to columns and add to results
        if tags is not None and tags.shape[0] > 0:
            df_tags = self._prepare_tags(tags)
            df.loc[df_tags.index, df_tags.columns] = df_tags

        # expand relations with ways
        if rels is not None and rels.shape[0] > 0:
            df_r = self._prepare_relations(rels)
            df_w = self._prepare_ways(ways)

            # drop duplicated ways also in df
            if df_w is not None:
                df = df.loc[~df.osmid.isin(df_w["memid"])]

            if query.topology:
                df_r = self.relation_topology(df_r)
                df_r = self.make_topo_geom(df_r)
                df = pd.merge(df, df_r, left_index=True, right_on="row", how="inner")

            elif query.geometry:
                df_r = self.relation_geometry(df_r, df_w)
                df = pd.merge(df, df_r, left_index=True, right_on="row", how="left")

            else:
                df = pd.merge(df, df_r, left_index=True, right_on="row", how="left")

            df = df.drop(columns="row")

        # add node geometries
        pts = df.loc[df.osmtype == 0]
        if query.geometry and len(pts) > 0:

            pts = self.make_points(pts.copy(), "osmid")
            df = df.set_index("osmid")
            pts = pts.set_index("osmid")
            df.loc[pts.index, "geometry"] = pts["geometry"]
            return df.sort_index()

        if query.geometry:
            df = df.set_geometry("geometry", crs=4326)

        return df.set_index("osmid").sort_index()

    def _prepare_tags(self, tags):
        df = pd.DataFrame(data=tags, columns=["osmpos", "tags", "values"])
        df["tags"] = self.map_to_strings(df["tags"])
        df["values"] = self.map_to_strings(df["values"])

        # unstack
        df = df.set_index(["osmpos", "tags"]).unstack("tags")
        df.columns = df.columns.get_level_values(1)

        return df

    def _prepare_relations(self, rels):
        df_r = pd.DataFrame(rels, columns=["row", "memid", "type", "role", "geom"])
        df_r["role"] = self.map_to_strings(df_r["role"])
        return df_r

    def _prepare_ways(self, ways):
        """create ways dataframe, add _s and _t columns with first and last node ids"""
        if ways is None:
            return None

        res = pd.DataFrame(ways, columns=["memid", "ptid"], dtype=np.uint64)
        res[["_s", "_t"]] = self.end_values(res, "memid", "ptid")
        return res

    # ---------------------------------
    # geometry

    def relation_geometry(self, df_r, ways):
        """Simplify relations as geometries, results with one row of each osmid and geometry type"""

        # dispatch geometries depending on geom type
        res = []
        res.append(self.make_points(df_r.loc[df_r.geom == 1].copy(), "memid"))
        res.append(self.make_lines(df_r.loc[df_r.geom == 2].copy()))
        res.append(self.make_areas(df_r.loc[df_r.geom == 3].copy(), ways))

        res = pd.concat(res, ignore_index=True).reset_index(drop=True)
        return res.drop(columns=["geom", "type", "role", "ptid"])

    def make_points(self, df, ptcol):
        coords = self.coords(df[ptcol])
        return points(df, 4326, coords).drop(columns=ptcol)

    def make_lines(self, df):
        coords = self.coords(df["memid"])
        return linestrings(df, 4326, coords, "row").drop(columns=["memid"])

    def make_areas(self, df, ways):
        """Add a polygon/multipolygon geometry column to a relation dataframe grouped by osm id"""

        res = []
        ringmax = 0

        # simple areas from ways, nodes already expanded
        mask = ~df.role.isin(["outer", "inner"])

        if mask.any():
            simple = df.loc[mask].rename(columns={"memid": "ptid"})
            simple["ring"] = simple["row"]
            simple["role"] = "outer"
            ringmax = simple["ring"].max()
            res.append(simple.drop(columns=["geom", "type"]))

        # simple areas from relations : one way and closed
        if ways is not None:
            areas = df.loc[~mask].copy()
            w = ways.drop_duplicates("memid")[["memid", "_s", "_t"]]
            areas = pd.merge(areas, w, on="memid", how="left")
            mask = areas["_s"] == areas["_t"]

        # expand closed ways
        if ways is not None and mask.any():
            closed = areas.loc[mask].drop(columns=["_s", "_t", "geom", "type"])
            closed = pd.merge(closed, ways, on="memid", how="left")
            closed["ring"] = _simple_ix(closed["memid"]) + ringmax + 1
            ringmax = closed["ring"].max()
            res.append(closed.drop(columns=["memid", "_s", "_t"]))

        # expand complex ways
        if ways is not None and not mask.all():
            areas = areas.loc[~mask].copy()

            # reorder rings and create ring indices
            cols = ["row", "role"]
            res_col = ["pos", "dir", "ring"]
            areas[res_col] = areas.groupby(cols, sort=False).apply(self._reorder_ring)
            areas["ring"] = _simple_ix(areas["row"]) + areas["ring"] + ringmax + 1

            # remove inner rings if multiple outer rings
            areas = self._drop_complex_rings(areas)

            w = ways.loc[ways.memid.isin(areas.memid)].copy()
            w["node_pos"] = self._position_ix(w, "memid")

            # reorder rows, if dir is -1, order is reversed
            areas = areas.drop(columns=["_s", "_t"])
            areas = pd.merge(areas, w, on="memid", how="left")
            areas["node_pos"] = areas["node_pos"] * areas["dir"]
            cols = ["row", "role", "ring", "pos", "node_pos"]
            areas = areas.sort_values(cols, kind="stable")

            # drop intermediate duplicated nodes
            areas = areas.loc[(areas.pos == 0) | (areas.node_pos != 0)]
            cols = ["node_pos", "dir", "pos", "geom", "type", "memid"]
            areas = areas.drop(columns=cols)

            # add node if last node in a ring is not the same as first
            areas = self._close_rings(areas, "ring")
            areas = areas.sort_values(["row", "role", "ring"], kind="stable")
            res.append(areas.drop(columns=["_s", "_t"]))

        areas = pd.concat(res, ignore_index=True)

        # polygon indices
        areas["poly"] = self._polygon_indices(areas)

        # create geometries
        coords = self.coords(areas["ptid"])
        areas = polygons(areas, 4326, coords, "ring", "poly", multi_indices="row")
        return areas.drop(columns=["ring", "poly"])

    @staticmethod
    def _reorder_ring(grp):
        """Add columns pos (way order in ring) and direction (1 = same as way, -1 reverse"""

        df = grp.assign(trav=False, pos=0, direction=1, ring=0)
        ix = df.head(1).index[0]
        node = df.loc[ix, "_t"]
        df.loc[ix, "trav"] = True
        l = len(df)

        pos = 1
        ring = 0

        while pos < l:
            mask = (~df.trav) & (df["_s"] == node)
            if mask.any():
                ix = df.loc[mask].index[0]
                node = df.loc[ix, "_t"]
                df.loc[ix, ["trav", "pos"]] = [True, pos]

            elif len(df.loc[(~df.trav) & (df["_t"] == node)]) > 0:
                ix = df.loc[(df["_t"] == node) & (~df.trav)].index[0]
                node = df.loc[ix, "_s"]
                df.loc[ix, ["trav", "direction", "pos"]] = [True, -1, pos]

            else:
                ring += 1
                ix = df.loc[~df.trav].head(1).index[0]
                node = df.loc[ix, "_t"]
                df.loc[ix, ["trav", "pos"]] = [True, pos]
                df.loc[~df.trav, "ring"] = ring

            pos += 1

        return df[["pos", "direction", "ring"]]

    @staticmethod
    def _close_rings(df, ringcol="ringid"):
        """Add an ending node equal to first node in ring if it does not exists"""

        closer = df.groupby(ringcol).agg(
            first=("ptid", "first"),
            last=("ptid", "last"),
            role=("role", "first"),
            row=("row", "first"),
        )
        cols = ["first", "role", "row"]
        closer = closer.loc[closer["first"] != closer["last"]][cols]
        closer = closer.rename(columns={"first": "ptid"})

        res = pd.concat([df, closer.reset_index()])
        return res

    @staticmethod
    def _drop_complex_rings(df):
        """Remove inner rings if multiple inner and multiple outer rings"""

        if "inner" not in df["role"]:
            return df

        dup = df.drop_duplicates("ring").groupby(["row", "role"]).size()
        dup = dup.unstack("role")
        dup = dup.loc[(dup.inner > 1) & (dup.outer > 1)]
        return df.loc[(df.role == "outer") | (~df.row.isin(dup.index))].copy()

    @staticmethod
    def _position_ix(df, column):
        """Create a position index, reset to 0 when column value changes"""
        return df.groupby(column).cumcount()

    @staticmethod
    def _polygon_indices(df):
        pix = df.index == 0
        pix |= df["row"] != df["row"].shift(1)
        pix |= (df["role"] == "outer") & (df["ring"] != df["ring"].shift(1))
        return pix.astype(int).cumsum() - 1

    # ---------------------------------
    # topology

    def make_topo_geom(self, topo):
        """Simplify relations as geometries, one row per topology segment"""
        coords = self.coords(topo["ptid"])
        res = linestrings(topo, 4326, coords, "ix")
        return res[["row", "geometry", "source", "target"]]

    def relation_topology(self, df):
        """Add topologoly to relations : segment ix index, source and target columns, duplicate end points"""

        cols = ["role", "type", "geom"]
        res = df.drop(columns=cols).rename(columns={"memid": "ptid"})
        res = res.reset_index(drop=True)
        res[["_s", "_t"]] = self.end_values(res, "row", "ptid")

        # mask of nodes on multiple ways
        dup = res.ptid.duplicated(keep=False)

        # mask of start and end node
        st = (res["ptid"] == res["_s"]) & (res["row"] != res["row"].shift(1))
        end = (res["ptid"] == res["_t"]) & (res["row"] != res["row"].shift(-1))
        res["ix"] = st | (dup & (~end))
        res["ix"] = res["ix"].astype(int)

        # insert segment rows
        dup_nodes = res.loc[dup & (~st) & (~end)].index.to_numpy()
        arr = np.insert(arr=res.index.to_numpy(), obj=dup_nodes, values=dup_nodes)
        res = res.reindex(arr).sort_index()
        res.loc[res.index.duplicated(keep="last"), "ix"] = 0

        res["ix"] = res["ix"].cumsum() - 1

        # reset values of start and end node
        res = res.drop(columns=["_s", "_t"]).reset_index(drop=True)
        res[["source", "target"]] = self.end_values(res, "ix", "ptid")

        return res

    @staticmethod
    def end_values(df, idcol, col):
        grp = df.groupby(idcol).agg(_s=(col, "first"), _t=(col, "last"))
        res = grp.loc[df[idcol]]
        res.index = df.index
        return res