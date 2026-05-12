import traceback

from quart import request

from astrbot.core import DEMO_MODE, logger, pip_installer
from astrbot.core.core_lifecycle import AstrBotCoreLifecycle
from astrbot.core.db.migration.helper import check_migration_needed_v4, do_migration_v4

from .route import Response, Route, RouteContext


class UpdateRoute(Route):
    def __init__(
        self,
        context: RouteContext,
        core_lifecycle: AstrBotCoreLifecycle,
    ) -> None:
        super().__init__(context)
        self.routes = {
            "/update/pip-install": ("POST", self.install_pip_package),
            "/update/migration": ("POST", self.do_migration),
        }
        self.core_lifecycle = core_lifecycle
        self.register_routes()

    async def do_migration(self):
        need_migration = await check_migration_needed_v4(self.core_lifecycle.db)
        if not need_migration:
            return Response().ok(None, "不需要进行迁移。").__dict__
        try:
            data = await request.json
            pim = data.get("platform_id_map", {})
            await do_migration_v4(
                self.core_lifecycle.db,
                pim,
                self.core_lifecycle.astrbot_config,
            )
            return Response().ok(None, "迁移成功。").__dict__
        except Exception as e:
            logger.error(f"迁移失败: {traceback.format_exc()}")
            return Response().error(f"迁移失败: {e!s}").__dict__

    async def install_pip_package(self):
        if DEMO_MODE:
            return (
                Response()
                .error("You are not permitted to do this operation in demo mode")
                .__dict__
            )

        data = await request.json
        package = data.get("package", "")
        mirror = data.get("mirror", None)
        if not package:
            return Response().error("缺少参数 package 或不合法。").__dict__
        try:
            await pip_installer.install(package, mirror=mirror)
            return Response().ok(None, "安装成功。").__dict__
        except Exception as e:
            logger.error(f"/api/update_pip: {traceback.format_exc()}")
            return Response().error(e.__str__()).__dict__
