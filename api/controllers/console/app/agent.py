from flask_restful import Resource, reqparse

from controllers.console import api
from controllers.console.app.wraps import get_app_model
from controllers.console.setup import setup_required
from controllers.console.wraps import account_initialization_required
from libs.helper import uuid_value
from libs.login import login_required
from models.model import AppMode
from services.agent_service import AgentService


class AgentLogApi(Resource):
    @setup_required
    @login_required
    @account_initialization_required
    @get_app_model(mode=[AppMode.AGENT_CHAT])
    def get(self, app_model):
        """Get agent logs"""
        parser = reqparse.RequestParser()
        parser.add_argument("message_id", type=uuid_value, required=True, location="args")
        parser.add_argument("conversation_id", type=uuid_value, required=True, location="args")

        args = parser.parse_args()

        return AgentService.get_agent_logs(app_model, args["conversation_id"], args["message_id"])


api.add_resource(AgentLogApi, "/apps/<uuid:app_id>/agent/logs")

#下面是集成AutoGen而增加的

from typing import Literal
from pydantic import BaseModel, Field
from typing_extensions import Annotated
from autogen.coding import LocalCommandLineCodeExecutor
import autogen
from autogen.cache import Cache

config_list = [
    {
        'model': 'gpt-4o',
        'api_key': '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',
        'tags': ['tool', '4o-tool'],
    }
]

llm_config = {
    "config_list": config_list,
    "timeout": 120,
}

gateway_assistant = autogen.AssistantAgent(
    name="gateway_assistant",
    system_message="你是一个人工助手，可以根据所具备的工具处理与模板管理相关的工作，请将详细的思考过程打印出来",
    llm_config=llm_config
)

gateway_userproxy = autogen.UserProxyAgent(
    name="gateway_userproxy",
    system_message="你是一个人工助手，可以帮助解决与网关管理的相关工作。你需要将具体的问题打印出来，尽可能详细的描述，这样助手才能了解到具体的问题",
    is_termination_msg=lambda x: x.get("content", "") and x.get("content", "").rstrip().endswith("TERMINATE"),
    human_input_mode="NEVER",
    max_consecutive_auto_reply=10,
    code_execution_config={
        "executor": LocalCommandLineCodeExecutor(work_dir="coding"),
    },
    default_auto_reply="TERMINATE"
)

import chromadb
#修改下面两个路径为本地路径
DOC_PATH = "/Users/Jian_1/Desktop/app1/PAC4200.pdf"
CHROMA_DB_PATH="/Users/Jian_1/Desktop/app1"
CHROMA_COLLECTION="gateway"
chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
collection = chroma_client.get_or_create_collection(name=CHROMA_COLLECTION)

from autogen.agentchat.contrib.retrieve_user_proxy_agent import RetrieveUserProxyAgent
rag_gateway_userproxy = RetrieveUserProxyAgent(
    name="rag_agent",
    system_message="你是一个人工助手，可以帮助解决与网关管理的相关工作。你需要将具体的问题打印出来，尽可能详细的描述，这样助手才能了解到具体的问题",
    human_input_mode="NEVER",
    max_consecutive_auto_reply=10,
    retrieve_config={
        "task": "qa",
        "docs_path": [
            DOC_PATH,
        ],
        "chunk_token_size": 2000,
        "model": config_list[0]["model"],
        "vector_db": "chroma",
        "overwrite": False,
        # 灵活使用这个，可能需要设置为False
        "get_or_create": True,
        "client": chroma_client,
        "collection_name": CHROMA_COLLECTION,
    },
    code_execution_config=False,
)

header = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Connection": "keep-alive",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36"
}

url = "http://117.185.89.18:14020/api/v3"

def struct_ret(result):
    import json
    content = json.loads(result.text)
    ret = {
        "status_code": result.status_code,
        "ok": content.get("ok", ""),
        "message": content.get("message", ""),
        "data": content.get("data", ""),
        "code"  : content.get("code", "")
    }
    return ret

@gateway_userproxy.register_for_execution()
@gateway_assistant.register_for_llm(description="根据模板id获取模板的详细信息")
def get_template_by_id(
    id: Annotated[str, "模板id"]
)-> dict:
    import requests
    result = requests.get(url + "/manager/profile/id/" + id, json={}, headers=header)
    return struct_ret(result)

@gateway_userproxy.register_for_execution()
@gateway_assistant.register_for_llm(description="获取所有模板信息")
def get_all_templates()-> dict:
    import requests
    result = requests.post(url + "/manager/profile/list", json={}, headers=header)
    return struct_ret(result)

@gateway_userproxy.register_for_execution()
@gateway_assistant.register_for_llm(description="创建模板")
def add_template(
    profileName: Annotated[str, "模板名称，不能包含空格"],
    remark: Annotated[str, "模板备注"]
)-> dict:
    import requests
    param = {
        "profileName": profileName,
        "remark": remark
    }
    result = requests.post(url + "/manager/profile/add", json=param, headers=header)
    return struct_ret(result)

@gateway_userproxy.register_for_execution()
@gateway_assistant.register_for_llm(description="编辑模板信息")
def update_template(
    id: Annotated[str, "ID (字符串类型，必填)"],
    profileName: Annotated[str, "模板名称 (字符串类型，必填，不能包含空格)"],
    enableFlag: Annotated[str, "启用标志 (字符串类型，必填，必须是 ENABLE 或 DISABLE)"],
    createTime: Annotated[str, "创建时间 (字符串类型，必填，默认值为当前时间)"] = None,
    operateTime: Annotated[str, "操作时间 (字符串类型，必填，默认值为当前时间)"] = None,
    remark: Annotated[str, "备注 (字符串类型，选填)"] = None,
    creatorId: Annotated[int, "创建者ID (整数类型，选填，默认值为0)"] = 0,
    creatorName: Annotated[str, "创建者名称 (字符串类型，选填，默认值为空字符串)"] = "",
    operatorId: Annotated[int, "操作员ID (整数类型，选填，默认值为0)"] = 0,
    operatorName: Annotated[str, "操作员名称 (字符串类型，选填，默认值为空字符串)"] = "",
    profileCode: Annotated[str, "模板编码 (字符串类型，选填，默认值为空字符串)"] = "",
    profileShareFlag: Annotated[str, "模板分享标志 (字符串类型，选填，默认值为 TENANT)"] = "TENANT",
    profileTypeFlag: Annotated[str, "模板类型标志 (字符串类型，选填，默认值为 USER)"] = "USER",
    groupId: Annotated[int, "组ID (整数类型，选填，默认值为0)"] = 0,
    signature: Annotated[str, "签名 (字符串类型，选填，默认值为空字符串)"] = "",
    version: Annotated[int, "版本 (整数类型，选填，默认值为1)"] = 1,
)-> dict:
    import requests
    from datetime import datetime
    if enableFlag not in ["ENABLE", "DISABLE"]:
        raise ValueError("enableFlag 必须是 'ENABLE' 或 'DISABLE'")
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    createTime = createTime if createTime is not None else current_time
    operateTime = operateTime if operateTime is not None else current_time
    param = {
        "id": id,
        "remark": remark,
        "creatorId": creatorId,
        "creatorName": creatorName,
        "createTime": createTime,
        "operatorId": operatorId,
        "operatorName": operatorName,
        "operateTime": operateTime,
        "profileName": profileName,
        "profileCode": profileCode,
        "profileShareFlag": profileShareFlag,
        "profileTypeFlag": profileTypeFlag,
        "groupId": groupId,
        "enableFlag": enableFlag,
        "signature": signature,
        "version": version
    }    
    result = requests.post(url + "/manager/profile/update", json=param, headers=header)
    return struct_ret(result)

@gateway_userproxy.register_for_execution()
@gateway_assistant.register_for_llm(description="根据id删除模板")
def delete_template_by_id(
    id: Annotated[str, "模板id"]
)-> dict:
    import requests
    result = requests.post(url + "/manager/profile/delete/" + id, json={}, headers=header)
    return struct_ret(result)

@gateway_userproxy.register_for_execution()
@gateway_assistant.register_for_llm(description="为模板增加点（即位号）")
def add_point(
    profileId: Annotated[str, "模板ID (字符串类型，必填)"],
    pointName: Annotated[str, "位号名称 (字符串类型，必填，不能包含空格)"],
    enableFlag: Annotated[str, "启用标志 (字符串类型，必填，必须是 ENABLE 或 DISABLE)"],
    remark: Annotated[str, "描述 (字符串类型，必填)"],
    rwFlag: Annotated[str, "读写标识 (字符串类型，必填，必须是 R, W, 或 RW)"],
    unit: Annotated[str, "单位 (字符串类型，必填，如果实在没有传递内容，可填写空字符串)"],
    pointTypeFlag: Annotated[str, "数据类型标识 (字符串类型，必填，必须是 STRING, BYTE, SHORT, INT, LONG, FLOAT, DOUBLE, BOOLEAN 中的一个)"],
    profileName: Annotated[str, "模板名称 (字符串类型，选填，默认值为空字符串，不能包含空格)"] = "",
    accrue: Annotated[str, "累积 (字符串类型，选填，默认值为空字符串)"] = "",
    format: Annotated[str, "格式 (字符串类型，选填，默认值为空字符串)"] = "",
    id: Annotated[str, "ID (字符串类型，选填，默认值为空字符串)"] = "",
    base: Annotated[str, "基础值 (字符串类型，选填，默认值为空字符串)"] = "",
    minimum: Annotated[str, "最小值 (字符串类型，选填，默认值为空字符串)"] = "",
    maximum: Annotated[str, "最大值 (字符串类型，选填，默认值为空字符串)"] = "",
    multipe: Annotated[str, "倍数 (字符串类型，选填，默认值为空字符串)"] = "",
    valueDecimal: Annotated[str, "小数位数 (字符串类型，选填，默认值为 1)"] = "1",
    baseValue: Annotated[str, "基础值 (字符串类型，选填，默认值为 1)"] = "1",
    multiple: Annotated[str, "倍数 (字符串类型，选填，默认值为 1)"] = "1"
)-> dict:
    import requests
    if enableFlag not in ["ENABLE", "DISABLE"]:
        raise ValueError("enableFlag 必须是 'ENABLE' 或 'DISABLE'")
    if rwFlag not in ["R", "W", "RW"]:
        raise ValueError("rwFlag 必须是 'R', 'W', 或 'RW'")
    valid_point_types = ["STRING", "BYTE", "SHORT", "INT", "LONG", "FLOAT", "DOUBLE", "BOOLEAN"]
    if pointTypeFlag not in valid_point_types:
        raise ValueError(f"pointTypeFlag 必须是 {valid_point_types} 中的一个")
    
    param = {
        "profileId": profileId,
        "pointName": pointName,
        "enableFlag": enableFlag,
        "remark": remark,
        "rwFlag": rwFlag,
        "pointTypeFlag": pointTypeFlag,
        "profileName": profileName,
        "accrue": accrue,
        "format": format,
        "id": id,
        "base": base,
        "minimum": minimum,
        "maximum": maximum,
        "unit": unit,
        "multipe": multipe,
        "valueDecimal": valueDecimal,
        "baseValue": baseValue,
        "multiple": multiple
    }
    result = requests.post(url + "/manager/point/add", json=param, headers=header)
    return struct_ret(result)

@gateway_userproxy.register_for_execution()
@gateway_assistant.register_for_llm(description="编辑点（即位号）信息")
def update_point(
    enableFlag: Annotated[str, "启用标志 (字符串类型，必填，必须是 ENABLE 或 DISABLE)"],
    id: Annotated[str, "ID (字符串类型，必填)"],
    pointName: Annotated[str, "位号名称 (字符串类型，必填，不能包含空格)"],
    pointTypeFlag: Annotated[str, "数据类型标识 (字符串类型，必填，必须是 STRING, BYTE, SHORT, INT, LONG, FLOAT, DOUBLE, BOOLEAN 中的一个)"],
    profileId: Annotated[str, "模板ID (字符串类型，必填)"],
    rwFlag: Annotated[str, "读写标识 (字符串类型，必填，必须是 R, W, 或 RW)"],
    unit: Annotated[str, "单位 (字符串类型，必填，如果实在没有传递内容，可填写空字符串)"],
    remark: Annotated[str, "备注 (字符串类型，选填)"] = None,
    baseValue: Annotated[str, "基础值 (字符串类型，选填，默认值为 1)"] = "1",
    createTime: Annotated[str, "创建时间 (字符串类型，必填，默认值为当前时间)"] = None,
    groupId: Annotated[int, "组ID (整数类型，选填，默认值为0)"] = 0,
    multiple: Annotated[str, "倍数 (字符串类型，选填，默认值为 1)"] = "1",
    valueDecimal: Annotated[str, "小数位数 (字符串类型，选填，默认值为 1)"] = "1",
)-> dict:
    import requests
    from datetime import datetime
    if enableFlag not in ["ENABLE", "DISABLE"]:
        raise ValueError("enableFlag 必须是 'ENABLE' 或 'DISABLE'")
    if rwFlag not in ["R", "W", "RW"]:
        raise ValueError("rwFlag 必须是 'R', 'W', 或 'RW'")
    valid_point_types = ["STRING", "BYTE", "SHORT", "INT", "LONG", "FLOAT", "DOUBLE", "BOOLEAN"]
    if pointTypeFlag not in valid_point_types:
        raise ValueError(f"pointTypeFlag 必须是 {valid_point_types} 中的一个")
    
    param = {
        "profileId": profileId,
        "pointName": pointName,
        "enableFlag": enableFlag,
        "remark": remark,
        "rwFlag": rwFlag,
        "pointTypeFlag": pointTypeFlag,
        "id": id,
        "unit": unit,
        "valueDecimal": valueDecimal,
        "baseValue": baseValue,
        "multiple": multiple,
        "createTime": createTime,
        "groupId": groupId
    }
    result = requests.post(url + "/manager/point/update", json=param, headers=header)
    return struct_ret(result)

@gateway_userproxy.register_for_execution()
@gateway_assistant.register_for_llm(description="获取模板下所有点（即位号）信息")
def get_profile_all_points(
    profileId: Annotated[str, "模板ID"]
)-> dict:
    import requests
    param = {
        "profileId": profileId
    }
    result = requests.post(url + "/manager/point/list", json=param, headers=header)
    return struct_ret(result)

@gateway_userproxy.register_for_execution()
@gateway_assistant.register_for_llm(description="根据id删除点（即位号）")
def delete_point_by_id(
    id: Annotated[str, "点（即位号）id"]
)-> dict:
    import requests
    result = requests.post(url + "/manager/point/delete/" + id, json={}, headers=header)
    return struct_ret(result)

@gateway_userproxy.register_for_execution()
@gateway_assistant.register_for_llm(description="获取所有驱动信息")
def get_all_drivers()-> dict:
    import requests
    result = requests.post(url + "/manager/driver/list", json={}, headers=header)
    return struct_ret(result)

@gateway_userproxy.register_for_execution()
@gateway_assistant.register_for_llm(description="获取所有设备信息")
def get_all_devices()-> dict:
    import requests
    result = requests.post(url + "/manager/device/list", json={}, headers=header)
    return struct_ret(result)

@gateway_userproxy.register_for_execution()
@gateway_assistant.register_for_llm(description="创建设备，设备需要关联驱动和模板")
def add_device(
    driverId: Annotated[str, "驱动ID (字符串类型，必填)"],
    deviceName: Annotated[str, "设备名称 (字符串类型，必填，不能包含空格)"],
    remark: Annotated[str, "描述 (字符串类型，必填)"],
    profileId: Annotated[str, "模板ID (字符串，必填)"],
    multi: Annotated[str, "存储类型 (字符串类型，选填，必须是 true或false中的一个，true代表结构数据，false代表单点数据)"] = "false",
)-> dict:
    import requests
    
    if multi not in ["true", "false"]:
        raise ValueError("multi 必须是 'true' 或 'false'")
    
    profileIds = []
    profileIds.append(profileId)
    param = {
        "driverId": driverId,
        "deviceName": deviceName,
        "remark": remark,
        "multi": multi,
        "profileIds": profileIds,
    }
    result = requests.post(url + "/manager/device/add", json=param, headers=header)
    return struct_ret(result)

@gateway_userproxy.register_for_execution()
@gateway_assistant.register_for_llm(description="更新设备信息")
def update_device(
    id: Annotated[str, "设备ID (字符串类型，必填)"],
    driverId: Annotated[str, "驱动ID (字符串类型，必填)"],
    deviceName: Annotated[str, "设备名称 (字符串类型，必填，不能包含空格)"],
    remark: Annotated[str, "描述 (字符串类型，必填)"],
    profileId: Annotated[str, "模板ID (字符串，必填)"],
    enableFlag: Annotated[str, "启用标志 (字符串类型，必填，必须是 ENABLE 或 DISABLE)"],
)-> dict:
    import requests
    from datetime import datetime
    if enableFlag not in ["ENABLE", "DISABLE"]:
        raise ValueError("enableFlag 必须是 'ENABLE' 或 'DISABLE'")
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    createTime = current_time
    operateTime = current_time
    
    profileIds = []
    profileIds.append(profileId)
    
    param = {
        "id": id,
        "driverId": driverId,
        "deviceName": deviceName,
        "remark": remark,
        "profileIds": profileIds,
        "enableFlag": enableFlag,
        "creatorId": 0,
        "creatorName": "",
        "createTime": createTime,
        "operatorId": 0,
        "operatorName": "",
        "operateTime": operateTime,
        "deviceCode": "",
        "groupId": 0,
        "signature": "",
        "version": 1
    }
    result = requests.post(url + "/manager/device/update", json=param, headers=header)
    return struct_ret(result)

@gateway_userproxy.register_for_execution()
@gateway_assistant.register_for_llm(description="获取设备的点（即位号）信息")
def get_device_all_points(
    deviceId: Annotated[str, "设备id"]
)-> dict:
    import requests
    result = requests.get(url + "/manager/point/device_id/" + deviceId, json={}, headers=header)
    return struct_ret(result)

@gateway_userproxy.register_for_execution()
@gateway_assistant.register_for_llm(description="根据id删除设备")
def delete_device_by_id(
    id: Annotated[str, "设备id"]
)-> dict:
    import requests
    result = requests.post(url + "/manager/device/delete/" + id, json={}, headers=header)
    return struct_ret(result)

@gateway_userproxy.register_for_execution()
@gateway_assistant.register_for_llm(description="修改设备设备下某个点（即位号）的配置，配置项是从站编号、功能码和偏移量")
def config_device_point(
    deviceId: Annotated[str, "设备ID (字符串类型，必填)"],
    pointId: Annotated[str, "位号ID (字符串类型，必填)"],
    slaveId: Annotated[str, "从站编号 (字符串类型，必填)"],
    functionCode: Annotated[str, "功能码 (字符串类型，必填)"],
    offset: Annotated[str, "偏移量 (字符串，必填)"],
)-> dict:
    import requests
    
    results = []
    result = requests.get(url + "/manager/device/id/" + deviceId, json={}, headers=header)
    device = struct_ret(result)["data"]
    driverId = device["driverId"]
    result = requests.get(url + "/manager/point_attribute/driver_id/" + str(driverId), json={}, headers=header)
    attributes = struct_ret(result)["data"]
    for attribute in attributes:
        param = None
        if attribute["attributeName"] == "slaveId":
            param = {
                "deviceId": deviceId,
                "pointId": pointId,
                "pointAttributeId": attribute["id"],
                "configValue": slaveId,
            }
        if attribute["attributeName"] == "functionCode":
            param = {
                "deviceId": deviceId,
                "pointId": pointId,
                "pointAttributeId": attribute["id"],
                "configValue": functionCode,
            }
        if attribute["attributeName"] == "offset":
            param = {
                "deviceId": deviceId,
                "pointId": pointId,
                "pointAttributeId": attribute["id"],
                "configValue": offset,
            }
        result = requests.post(url + "/manager/point_attribute_config/add", json=param, headers=header)
        results.append(struct_ret(result))
    return results

@gateway_userproxy.register_for_execution()
@gateway_assistant.register_for_llm(description="通过查询文档获取设备点位的具体配置信息")
def get_device_points_config_from_document(
    problem: Annotated[str, "查询内容 (字符串类型，必填)"],
)-> dict:
    chat_result = rag_gateway_userproxy.initiate_chat(
        gateway_assistant, message = rag_gateway_userproxy.message_generator, problem = problem
    )
    return chat_result.chat_history[-1]

def format_response(chat_result):
    history = chat_result.chat_history
    
    if not history:
        return "AutoGenStart无法回答您的问题，请重新提问AutoGenEnd"
    
    if len(history) > 0:
        result_1 = history[-1]["content"]
        if result_1 != "TERMINATE":
            return "AutoGenStart" + result_1 + "AutoGenEnd"
        elif len(history) > 1:
            result_2 = history[-2]["content"]
            return "AutoGenStart" + result_2 + "AutoGenEnd"
        else:
            return "AutoGenStart无法回答您的问题，请重新提问AutoGenEnd"
    else:
        return "AutoGenStart无法回答您的问题，请重新提问AutoGenEnd"
    

class BasicApi(Resource):
    def post(self, message: str):
        """
        执行基本的增删改查
        """
        message += "！！！注意，如果无法确认被查询、新增、更新、删除的对象是哪种种类别（如设备、模板、点位（即位号）），应该调用get_all_templates、get_all_devices，有必要的话再调用get_profile_all_points去寻找这个对象！！！"
        gateway_assistant.reset()
        chat_result = gateway_userproxy.initiate_chat(
            gateway_assistant, message = message, summary_method = "reflection_with_llm"
        )
        
        result = {
            "chat_result": format_response(chat_result)
        }

        return result
    
class RAGChatApi(Resource):
    def post(self, problem: str):
        """
        从文档中查询内容
        """
        gateway_assistant.reset()
        chat_result = rag_gateway_userproxy.initiate_chat(
            gateway_assistant, message = rag_gateway_userproxy.message_generator, problem = problem
        )
        
        result = {
            "chat_result": format_response(chat_result)
        }

        return result
from flask import request
class OneStepApi(Resource):
    def post(self):
        """
        添加所有配置
        """
        data = request.get_json()
        
        device_name = data.get("device_name")
        device_points = data.get("device_points")
        others = data.get("others")
        
        if not device_name:
            result = {
                "chat_result": "AutoGenStart需要提供需要配置的设备名称AutoGenEnd"
            }
            return result
        if not device_points:
            result = {
                "chat_result": "AutoGenStart需要提供需要配置的设备点位AutoGenEnd"
            }
            return result
        
        gateway_assistant.reset()
        chat_result = gateway_userproxy.initiate_chat(
            gateway_assistant, message="本次数据采集的对象是" + device_name +"。"
            "先在文档中查询设备的点位配置，本次需要采集的点位包括" + device_points + "，（调用get_device_points_config_from_document工具）。"
            "根据点位配置创建模板，然后为模板创建点位，（调用add_template、add_point等工具）。"
            "接着创建设备，如果涉及到设备的驱动，则需要从文档中进行查找，（调用add_device等工具）。"
            "最后，根据文档中的点位配置依次配置点位信息，（这里需要先调用get_device_all_points，找到设备有哪些需要配置的点位，然后再调用config_device_point进行配置）。"
            "生成的各种字符串的命名尽量使用中文，其他要求和说明如下：" + others
            , summary_method="reflection_with_llm"
        )
        
        result = {
            "chat_result": format_response(chat_result)
        }

        return result

#测试可访问http://localhost:5001/console/api/apps/agent/autogen/basic_chat/hello
api.add_resource(BasicApi, "/apps/agent/autogen/http/v1/basic_chat/<string:message>")
api.add_resource(RAGChatApi, "/apps/agent/autogen/http/v1/rag_chat/<string:problem>")
api.add_resource(OneStepApi, "/apps/agent/autogen/http/v1/one_step")


