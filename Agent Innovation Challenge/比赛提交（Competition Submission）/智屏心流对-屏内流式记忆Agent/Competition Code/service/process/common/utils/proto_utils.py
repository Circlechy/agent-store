import json

from google.protobuf import json_format


class ProtoUtils:
    @staticmethod
    def to_dict(message) -> dict:
        return json_format.MessageToDict(message)

    @staticmethod
    def to_json(message) -> str:
        return json.dumps(ProtoUtils.to_dict(message), ensure_ascii=False)
