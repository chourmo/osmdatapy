import threading
import asyncio
import aiohttp
import os
import pandas as pd


class RunThread(threading.Thread):
    def __init__(self, func, args, kwargs):
        self.func = func
        self.args = args
        self.kwargs = kwargs
        super().__init__()

    def run(self):
        self.result = asyncio.run(self.func(*self.args, **self.kwargs))


def run_async(func, *args, **kwargs):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        thread = RunThread(func, args, kwargs)
        thread.start()
        thread.join()
        return thread.result
    else:
        return asyncio.run(func(*args, **kwargs))


async def _download(url: str, alternate_url: str, name: str) -> bytes:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                content = await resp.read()
                return content

            elif alternate_url is not None:
                async with session.get(alternate_url) as resp2:
                    if resp2.status == 200:
                        content = await resp2.read()
                        return content
                    else:
                        print("{0} is missing, error {1}".format(name, resp2.status))
                        return None
            else:
                print("{0} is missing, error {1}".format(name, resp.status))
                return None


async def _write(content: bytes, name: str, path: str, file_ext: str) -> None:
    with open(os.path.join(path, name + file_ext), "wb") as f:
        if content is not None:
            f.write(content)


async def _get_url(urls, name, path, file_ext) -> None:
    if len(urls) > 1:
        content = await _download(urls[0], urls[1], name)
    else:
        content = await _download(urls[0], None, name)
    await _write(content, name, path, file_ext)


async def _download_urls(urls, path, file_ext):
    """download and save urls dictionary of save name : [one or two urls] at path"""

    tasks = [_get_url(v, k, path, file_ext) for k, v in urls.items()]
    return await asyncio.gather(*tasks)


class Datasource:
    """
    Abstract class for GTFS datasources

    Args :
        content : short description of data source content
        license : optional license url for datasource (can be a single url, list of urls or dictionary of subsources:license)
        content_url : optional url to read about the data source
        places : if true, datasource can return data by place name
        file_extension : file extension
    """

    def __init__(self, content, license, content_url, places, file_ext=''):

        self.content = content
        self.license = license
        self.content_url = content_url
        self.places = places
        self.file_extension=file_ext

    def download(self, path, data_type=None, place=None, rename=None, compress=False):
        """
        donload data from datasource and save to path, returns a list path

        args:
            path : directory to save into
            data_type : data_type to get from datasource
            place : optional string or list of strings, save file with place name except if rename is not False
            rename : if not None, file name or list of file names, must be same size as places
            compress : zip file if set to True
        """

        if isinstance(place, list):

            if rename is not None:
                if not isinstance(rename, list):
                    raise ValueError("rename must be a list if place is a list")
                if len(rename) != len(place):
                    raise ValueError(
                        "rename must have the same size as place if place is a list"
                    )

            if rename is not None:
                urls = {rename[i]: self._get_url(data_type, pl) for i, pl in enumerate(place)}
            else:
                urls = {pl: self._get_url(data_type, pl) for pl in place}
        else:
            if rename is not None:
                if not isinstance(rename, str):
                    raise ValueError("rename must be a string if place is a string")
                urls = {rename: self._get_url(data_type, place)}
            else:
                urls = {place: self._get_url(data_type, place)}

        # download and save urls, optionaly rename
        run_async(_download_urls, urls, path, self.file_extension)

        return [os.path.join(path,k+ self.file_extension) for k in urls.keys()]

    # ---------------------------
    # function to subclass

    def valid_names(self):
        return None

    def _get_url(self, data_type, place):
        """function to replace by subclass, return a download url or tuple of (base url, alternate url) for data_type and place"""
        return None

    # ---------------------------
    # utilities

    def _zip_filename(self, name):

        if name[:-4] != ".zip":
            return name + ".zip"
        else:
            return name

    def expand_json(self, df, json, subset=None, unstack=False):
        """
        replace a dataframe with the expanded json values
        optionaly only keep subset of the expanded json columns and unstack columns
        """

        if subset is not None and unstack:
            raise ValueError("subset cannot be set when unstack is True")

        # reset index to make a monotically increasing index
        res = df.copy()
        res.index.name = "_ix"
        res = res.reset_index()

        expanded = pd.json_normalize(df[json])
        del res[json]

        if unstack:
            expanded = expanded.unstack().dropna()
            expanded = expanded.reset_index(level=0, drop=True).sort_index()
            expanded = expanded.to_frame(json)

        if subset is not None:
            expanded = expanded[subset]

        res = pd.merge(res, expanded, left_index=True, right_index=True, how="outer")
        res = res.set_index("_ix")
        res.index.name = df.index.name

        return res

    def comparable_string(self, df, drop_characters=["'", "’"]):
        """make string more easily comparable"""

        res = df.str.upper()
        res = res.str.normalize(form="NFC")
        for c in drop_characters:
            res = res.str.replace(c, "")
        return res