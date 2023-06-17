OPENAI_API_KEY = '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'

# REDIS_URL = 'redis://default:7d5927dcb2994809b4a06e12d3554471@localhost:6379/0'
REDIS_URL = 'redis://localhost:6379/0'
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_USER = 'default'
REDIS_PASSWORD = '7d5927dcb2994809b4a06e12d3554471'

# sandbox
WECHAT_ADMIN_APPID = 'wx922b49ce701c37f5'
WECHAT_ADMIN_SECRET = 'bb09404753f7b1d95d149826d2ed3c18'

# xunbao
# WECHAT_ADMIN_APPID = 'wx8d177cf445f8365e' 
# WECHAT_ADMIN_SECRET = 'dcdffc1198e5ce1a12569b244e0b9e51'

WECHAT_BOT_TOKEN = 'unicornrosesrainbows'

VOICE_AI_USER_ID = 'M0vdbMgTuRYNCeVMVzbQL7oSUkr1'
VOICE_AI_API_KEY = 'ab8c0dadb2684c6d818e47620d29985b'

POSTGRES_USER = 'postgres'
POSTGRES_PASSWORD = 'VL6Dees2mISf6CP'
POSTGRES_HOST = 'white-dream-1562.internal'
POSTGRES_PORT = 5432
# SQLALCHEMY_DATABASE_URL = 'postgresql://postgres:VL6Dees2mISf6CP@localhost:5432/wechatbot_dev'

SQLALCHEMY_DATABASE_URL = 'postgresql://postgres:postgres@localhost:5432/wechatbot_dev'

ENV = 'dev'
REDIS_KEY_PREFIX = ENV + '_'


#   Username:    postgres
#   Password:    VL6Dees2mISf6CP
#   Hostname:    white-dream-1562.internal
#   Flycast:     fdaa:2:5c9d:0:1::3
#   Proxy port:  5432
#   Postgres port:  5433
#   Connection string: postgres://postgres:VL6Dees2mISf6CP@white-dream-1562.flycast:5432