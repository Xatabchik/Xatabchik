from aiogram import Router, F, types

router = Router()


@router.callback_query(F.data == "mod:example_module:ping")
async def example_ping(callback: types.CallbackQuery) -> None:
    await callback.answer("Pong from example_module")
    await callback.message.answer("Example module says hi.")
