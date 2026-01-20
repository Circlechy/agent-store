from enum import Enum


class DetectType(Enum):
    FOOD = "food"
    PERSONAL = "personal"


FOOD_DETECT_STR: str = 'mango. litchi.'
PERSONAL_DETECT_STR: str = 'ID card. work card. card. passport. key. eyeglasses. eyewear. glasses. wallet. earphones. earbuds. cellphone. phone. drinking vessel. watch. bottle. thermos. lipstick. charger. charging cable. car. wifi. cross. crucifix. phone number. address. name. email. password.'

TARGET_LABELS_EN_ZH_DICT = {
    "mango": "芒果",
    "litchi": "荔枝",
}

UG_DOCUMENTS = [
    {
        "caption": """```json
{
"起点": "",
"地点": "朋友家里",
"事件描述": "在朋友家里聊天打牌",
"发生日期": "",
"持续时间": "",
"参与人": [
"带着毛茸茸帽子的朋友"
],
"event_id": 93,
"type": "social_events"
}
```"""
    },
    {
        "caption": """```json
{
"起点": "",
"地点": "星巴克",
"事件描述": "和穿着灰色衣服男士一起喝咖啡",
"发生日期": "",
"持续时间": "",
"参与人": [
"穿着灰色衣服的男士"
],
"event_id": 92,
"type": "social_events"
}
```"""
    }
]
