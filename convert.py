from typing import Any, List
import re
import numpy as np
import pandas as pd
import sys
import pathlib as pl
import datetime as dt
from dataclasses import dataclass

DEFAULT_CCW_DIR = r"./CCW/"
DEFAULT_S5K_DIR = r"./S5K/"

style_float = ["FLOAT", "REAL"]
timer_datatypes = ["TON", "TOF"]


@dataclass
class TagInfo:
    xml_tag: str = "Tag"
    name: str = ""
    datatype: str = ""
    radix: str = ""
    access: str = ""
    desc: str = ""
    data: str = ""
    # will not show for program tags
    usage: str = ""
    required: str = ""
    visible: str = ""

    def __setitem__(self, name: str, value: Any) -> None:
        if name == "access":
            if value == "Read":
                value = "Read Only"
            elif value == "Write":
                value = "Read/Write"
            self.access = f'ExternalAccess="{value}"'
        elif name == "datatype":
            self.datatype = f'DataType="{value}"'
        elif name in ["radix", "usage", "required", "visible", "name"]:
            setattr(self, name, f'{name.capitalize()}="{value}"')
        elif name == "desc" and value:
            self.desc = (
                '<Description>\n'
                f'<![CDATA[{value}]]>\n'
                '</Description>\n'
            )
        else:
            setattr(self, name, value)


@dataclass
class ParamInfo(TagInfo):

    def __post_init__(self):
        self.xml_tag = "Parameter"


def timestamp_to_s5k_format(timestamp) -> str:
    return timestamp.strftime("%a %b %d %H:%M:%S %Y")


def s5k_header(timestamp: dt.datetime) -> str:
    return f"""remark,CSV-Import-Export,,,,,
remark,Date = {timestamp_to_s5k_format(timestamp)},,,,,
remark,Version = RSLogix 5000 v33.01,,,,,
remark,Owner = ,,,,,
remark,Company = ,,,,,
0.3,,,,,,
"""


def s5k_addon_header(df_s5k: pd.DataFrame, name: str, controller_name: str, timestamp: str) -> str:
    return f"""
<RSLogix5000Content SchemaRevision="1.0" SoftwareRevision="33.01" TargetName="{name}" TargetType="" ContainsContext="true"  ExportDate="{timestamp_to_s5k_format(timestamp)}" ExportOptions="References NoRawData L5KData DecoratedData Context Dependencies ForceProtectedEncoding AllProjDocTrans">
<Controller Use="Context" Name="{controller_name}">
"""


def s5k_L5X_content_generate(df_s5k: pd.DataFrame, name: str, controller_name: str, timestamp: dt.datetime, type_: str):
    """
    type_: "program" or "addon"
    """
    target_type = ""
    body = ""
    target_revision = ""
    if type_ == "program":
        target_type = "Program"
        body = (
            '<Programs Use="Context">\n'
            f'<Program Use="Target" Name="{name}" TestEdits="false" Disabled="false" UseAsFolder="false">\n'
            '<Tags>\n'
            f'{convert_tags(df_s5k, type_)}\n'
            '</Tags>\n'
            '<Routines>\n'
            '</Routines>\n'
            '</Program>\n'
            '</Programs>\n'
        )
    elif type_ == "addon":
        target_type = "AddOnInstructionDefinition"
        target_revision = 'TargetRevision="1.0"'
        user = "Someone\\Special"
        body = (
            '<AddOnInstructionDefinitions Use="Context">\n'
            f'<AddOnInstructionDefinition Use="Target" Name="{name}" Revision="1.0" ExecutePrescan="false" ExecutePostscan="false" ExecuteEnableInFalse="false" CreatedDate="{timestamp.isoformat()}" CreatedBy="{user}" EditedDate="{timestamp.isoformat()}" EditedBy="{user}" SoftwareRevision="v33.01">\n'
            '<Parameters>\n'
            f'{convert_tags(df_s5k, type_)}\n'
            '</Parameters>\n'
            '<LocalTags/>\n'
            '<Routines>\n'
            '<Routine Name="Logic" Type="RLL"/>\n'
            '</Routines>\n'
            '</AddOnInstructionDefinition>\n'
            '</AddOnInstructionDefinitions>\n'
        )

    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<RSLogix5000Content SchemaRevision="1.0" SoftwareRevision="33.01" TargetName="{name}" TargetType="{target_type}" '
        f'{target_revision} TargetLastEdited="{timestamp.isoformat()}" ContainsContext="true" '
        f'ExportDate="{timestamp_to_s5k_format(timestamp)}" '
        'ExportOptions="References NoRawData L5KData DecoratedData Context Dependencies ForceProtectedEncoding AllProjDocTrans">\n'
        f'<Controller Use="Context" Name="{controller_name}">\n'
        '<DataTypes Use="Context"/>\n'
        f'{body}\n'
        '</Controller>\n'
        '</RSLogix5000Content>\n'
    )


def convert_tags(df_s5k: pd.DataFrame, type_: str) -> str:
    tags = []
    output = ''
    info_type = None
    if type_ == "program":
        info_type = TagInfo
    elif type_ == "addon":
        info_type = ParamInfo
        enable_in = ParamInfo()
        enable_in['name'] = "EnableIn"
        enable_in['datatype'] = "BOOL"
        enable_in['radix'] = "Decimal"
        enable_in['access'] = "Read Only"
        enable_in['desc'] = "Enable Input - System Defined Parameter"
        enable_in['usage'] = "Input"
        enable_in['required'] = "false"
        enable_in['visible'] = "false"
        enable_out = ParamInfo()
        enable_out['name'] = "EnableOut"
        enable_out['datatype'] = "BOOL"
        enable_out['radix'] = "Decimal"
        enable_out['access'] = "Read Only"
        enable_out['desc'] = "Enable Output - System Defined Parameter"
        enable_out['usage'] = "Output"
        enable_out['required'] = "false"
        enable_out['visible'] = "false"
        tags.extend([enable_in, enable_out])

    for t in df_s5k.itertuples():
        tag: TagInfo = info_type()
        tag['name'] = t.NAME
        tag['datatype'] = t.DATATYPE
        attributes = t.ATTRIBUTES
        pattern_radix = ".*RADIX := (\w+).*"
        pattern_access = ".*ExternalAccess := ([\w\/]+).*"
        m = re.search(pattern_radix, attributes)
        if m:
            tag['radix'] = m.groups()[0]
        m = re.search(pattern_access, attributes)
        if m and not t.DATATYPE == "TIMER":
            tag['access'] = m.groups()[0]
        if t.DATATYPE == "TIMER":
            data = (
                '<Data Format="L5K">\n'
                '<![CDATA[[0,0,0]]]>\n'
                '</Data>\n'
                '<Data Format="Decorated">\n'
                '<Structure DataType="TIMER">\n'
                '<DataValueMember Name="PRE" DataType="DINT" Radix="Decimal" Value="0"/>\n'
                '<DataValueMember Name="ACC" DataType="DINT" Radix="Decimal" Value="0"/>\n'
                '<DataValueMember Name="EN" DataType="BOOL" Value="0"/>\n'
                '<DataValueMember Name="TT" DataType="BOOL" Value="0"/>\n'
                '<DataValueMember Name="DN" DataType="BOOL" Value="0"/>\n'
                '</Structure>\n'
                '</Data>\n'
            )
        else:
            data = (
                '<Data Format="L5K">\n'
                '<![CDATA[0]]>\n'
                '</Data>\n'
                '<Data Format="Decorated">\n'
                f'<DataValue {tag.datatype} {tag.radix} Value="0"/>\n'
                '</Data>\n'
            )
        if tag.xml_tag == "Tag":
            tag['data'] = data
        elif t.DATA:
            tag['data'] = t.DATA
        tag['desc'] = t.DESCRIPTION

        if isinstance(tag, ParamInfo):
            tag['usage'] = t.USAGE
            tag['required'] = "true"
            if t.USAGE == "Local":
                tag['required'] = "false"
            tag['visible'] = "true"

        tags.append(tag)

    for tag in tags:
        xml = (
            f'<{tag.xml_tag} {tag.name} TagType="Base" {tag.datatype} '
            f'{tag.radix} {tag.access} {tag.usage} {tag.required} {tag.visible}>\n'
            f'{tag.desc}'
            f'{tag.data}'
            f'</{tag.xml_tag}>\n'
        )
        output += xml
    return output

# <Routine Name="Air_Purge_Sequence_Routine" Type="RLL">
# <RLLContent>
# <Rung Number="0" Type="N">
# <Text>
# <![CDATA[;]]>
# </Text>
# </Rung>
# </RLLContent>
# </Routine>


def extract_timer_vars(df: pd.DataFrame):
    df_timers = pd.DataFrame(columns=df.columns)
    for dtype in timer_datatypes:
        df_t = df[df["Data Type"] == dtype]
        df_timers = pd.concat([df_timers, df_t])
    for name in df_timers["Name"]:
        to_drop = df[df["Name"].str.startswith(f"{name}.")]
        df.drop(to_drop.index, inplace=True)


def find_and_convert_vars(dirpath_ccw_vars: str, dirpath_s5k_tags: str):
    if not dirpath_ccw_vars or not dirpath_s5k_tags:
        raise ValueError("Required: 1. path to directory containing CCW variable exports, 2. path to directory to put converted Studio 5000 tags")
    ccw_dir = pl.Path(dirpath_ccw_vars)
    if not ccw_dir.exists():
        raise FileNotFoundError(f"CCW folder '{ccw_dir}' does not exist")
    s5k_dir = pl.Path(dirpath_s5k_tags)
    if not s5k_dir.exists():
        raise FileNotFoundError(f"S5k converted tags folder '{s5k_dir}' does not exist")

    # find excel files for ccw vars
    for var_file in ccw_dir.glob(r"*.xlsx"):
        # skip locked files or w/e
        if var_file.name.startswith("~$"):
            continue
        convert(var_file, s5k_dir)


def insert_s5k_header(tags_path: pl.Path) -> str:
    original: List[str] = None
    with open(tags_path, "r") as f:
        original = f.readlines()
    with open(tags_path, "w") as f:
        f.write(s5k_header(dt.datetime.now()))
        f.writelines(original)


def vars_to_tags(df_ccw: pd.DataFrame) -> pd.DataFrame:
    def get_dimension(datatype: str, dimension: str) -> int:
        dim_num = 0
        pattern = "\[(\d+)\.\.(\d+)\]"
        m = re.search(pattern, dimension)
        if m:
            frm, to = map(int, m.groups())
            if datatype == "BOOL":
                dim_num = int(np.ceil((to - frm) / 32) * 32)
            else:
                dim_num = to - frm
        return dim_num

    def apply_datatype_if_different(datatype: str, dimension: str) -> str:
        dim_num = get_dimension(datatype, dimension)
        dim = ""
        # if dim_num > 0:
        #     dim = f"[{dim_num}]"
        if datatype in timer_datatypes:
            return "TIMER"
        if datatype == "TIME":
            return "DINT" + dim
        return datatype + dim

    # def apply_scope_if_different(datatype: str):
    #     if datatype in timer_datatypes:
    #         return "Sequencer"
    #     return ""

    def apply_attributes(datatype: str, read_write: str) -> str:
        try:
            rw = read_write.replace('ReadWrite', 'Read/Write')
        except AttributeError as e:
            rw = "Read/Write"
        if datatype in timer_datatypes:
            return f"{{Constant := false, ExternalAccess := {rw}}}"
        else:
            style = "Float" if datatype in style_float else "Decimal"
            return f"{{RADIX := {style}, Constant := false, ExternalAccess := {rw}}}"

    def apply_usage(direction: str):
        if direction == "VarInput":
            return "Input"
        if direction == "VarOutput":
            return "Output"
        return "Local"

    def apply_data(datatype: str, dimension: str) -> str:
        dim_num = get_dimension(datatype, dimension)
        # will need to match different type's representations
        if "BOOL" == datatype and dim_num > 0:
            return "[" + ",".join(['2#0']*dim_num) + "]"

        return ""

    def apply_dimension(datatype: str, dimension: str) -> int:
        return get_dimension(datatype, dimension)

    if df_ccw.empty:
        return pd.DataFrame()
    df_ccw = df_ccw[~df_ccw["Name"].str.contains('\[\d+\]')]
    extract_timer_vars(df_ccw)
    df_ccw.fillna("", inplace=True)
    df_ccw = df_ccw.astype(str)
    df_s5k = pd.DataFrame(
        columns=["TYPE", "SCOPE", "NAME", "DESCRIPTION", "DATATYPE", "SPECIFIER", "ATTRIBUTES", "USAGE"]
    )

    df_s5k[["NAME", "DESCRIPTION"]] = df_ccw[["Name", "Comment"]]
    df_s5k["DIMENSION"] = df_ccw.apply(lambda x: apply_dimension(datatype=x["Data Type"], dimension=x["Dimension"]), axis=1)
    df_s5k["DATATYPE"] = df_ccw.apply(lambda x: apply_datatype_if_different(datatype=x["Data Type"], dimension=x["Dimension"]), axis=1)
    # df_s5k["SCOPE"] = df_ccw.apply(lambda x: apply_scope_if_different(datatype=x["Data Type"]), axis=1)
    df_s5k["TYPE"] = "TAG"
    df_s5k["SCOPE"] = ""
    df_s5k["SPECIFIER"] = ""
    df_s5k["ATTRIBUTES"] = df_ccw.apply(lambda x: apply_attributes(datatype=x["Data Type"], read_write=x["Attribute"]), axis=1)
    df_s5k["USAGE"] = df_ccw.apply(lambda x: apply_usage(direction=x["Direction"]), axis=1)
    df_s5k["DATA"] = ""
    # df_s5k["DATA"] = df_ccw.apply(lambda x: apply_data(datatype=x["Data Type"], dimension=x["Dimension"]), axis=1)
    df_s5k.fillna("", inplace=True)
    df_s5k = df_s5k.astype(str)
    return df_s5k


def convert(file_ccw_vars: pl.Path, dirpath_s5k_converted: pl.Path):
    df_ccw = pd.read_excel(file_ccw_vars, skiprows=[1])
    df_s5k = vars_to_tags(df_ccw)

    if not df_s5k.empty:
        convert_to_s5k_tags(df_s5k, file_ccw_vars, dirpath_s5k_converted)
        convert_to_s5k_program(df_s5k, file_ccw_vars, dirpath_s5k_converted)
        convert_to_s5k_addon(df_s5k, file_ccw_vars, dirpath_s5k_converted)


def convert_to_s5k_tags(df_s5k: pd.DataFrame, file_ccw_vars: pl.Path, dirpath_s5k_converted: pl.Path):
    tags_filename = file_ccw_vars.name.replace(".xlsx", "") + "_tags.csv"
    tags_path = dirpath_s5k_converted.joinpath(tags_filename)
    df_s5k.drop(columns=["USAGE"]).to_csv(tags_path, index=False)
    insert_s5k_header(tags_path)


def convert_to_s5k_program(df_s5k: pd.DataFrame, file_ccw_vars: pl.Path, dirpath_s5k_converted: pl.Path):
    program_name = file_ccw_vars.name.replace(".xlsx", "")
    program_filename = program_name + "_program.L5X"
    program_path = dirpath_s5k_converted.joinpath(program_filename)
    with open(program_path, 'w') as f:
        f.write(s5k_L5X_content_generate(df_s5k, program_name, "Phil", dt.datetime.now(), "program"))


def convert_to_s5k_addon(df_s5k: pd.DataFrame, file_ccw_vars: pl.Path, dirpath_s5k_converted: pl.Path):
    addon_name = file_ccw_vars.name.replace(".xlsx", "")
    addon_filename = addon_name + "_addon.L5X"
    addon_path = dirpath_s5k_converted.joinpath(addon_filename)
    with open(addon_path, 'w') as f:
        f.write(s5k_L5X_content_generate(df_s5k, addon_name, "Phil", dt.datetime.now(), "addon"))


if __name__ == "__main__":
    dirpath_ccw_vars = DEFAULT_CCW_DIR
    dirpath_s5k_tags = DEFAULT_S5K_DIR
    if len(sys.argv) >= 3:
        dirpath_ccw_vars, dirpath_s5k_tags = sys.argv[1:]
    find_and_convert_vars(dirpath_ccw_vars, dirpath_s5k_tags)
