from functools import lru_cache
from .session import EntityType, Entity

_sentinel = object()


class EntityCache:
    def __init__(
        self, hash_map: dict = _sentinel, self_id: int = None, self_bot: bool = None
    ):
        self.hash_map = {} if hash_map is _sentinel else hash_map
        self.self_id = self_id
        self.self_bot = self_bot
        self._access_cache = {}

    def set_self_user(self, id, bot, hash):
        self.self_id = id
        self.self_bot = bot
        if hash:
            self.hash_map[id] = (hash, EntityType.BOT if bot else EntityType.USER)

    def get(self, id):
        if id in self._access_cache:
            return self._access_cache[id]

        result = self.hash_map.get(id)
        if result is None:
            return None

        hash, ty = result
        entity = Entity(ty, id, hash)
        if len(self._access_cache) < 1000:
            self._access_cache[id] = entity
        return entity

    def extend(self, users, chats):
        cache_updated = False
        for u in users:
            if getattr(u, "access_hash", None) and not u.min:
                self.hash_map[u.id] = (
                    u.access_hash,
                    EntityType.BOT if u.bot else EntityType.USER,
                )
                cache_updated = True

        for c in chats:
            if getattr(c, "access_hash", None) and not getattr(c, "min", None):
                ty = (
                    EntityType.MEGAGROUP
                    if c.megagroup
                    else (
                        EntityType.GIGAGROUP
                        if getattr(c, "gigagroup", None)
                        else EntityType.CHANNEL
                    )
                )
                self.hash_map[c.id] = (c.access_hash, ty)
                cache_updated = True

        if cache_updated:
            self._access_cache.clear()

    def put(self, entity):
        self.hash_map[entity.id] = (entity.hash, entity.ty)
        if len(self._access_cache) < 1000:
            self._access_cache[entity.id] = entity

    def retain(self, filter):
        self.hash_map = {k: v for k, v in self.hash_map.items() if filter(k)}
        self._access_cache = {k: v for k, v in self._access_cache.items() if filter(k)}

    def __len__(self):
        return len(self.hash_map)
