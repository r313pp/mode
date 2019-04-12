import asyncio
import pytest
from mode.utils.futures import (
    StampedeWrapper,
    done_future,
    maybe_async,
    maybe_cancel,
    stampede,
)
from mode.utils.mocks import Mock


class X:
    commit_count = 0

    @stampede
    async def commit(self):
        self.commit_count += 1
        await asyncio.sleep(0.5)
        return self.commit_count


async def call_commit(x):
    return await x.commit()


@pytest.mark.asyncio
async def test_stampede():
    x = X()
    assert all(r == 1 for r in await asyncio.gather(*[
        call_commit(x) for _ in range(100)]))
    assert x.commit_count == 1
    assert all(r == 2 for r in await asyncio.gather(*[
        call_commit(x) for _ in range(100)]))
    assert x.commit_count == 2
    assert await x.commit() == 3
    assert x.commit_count == 3

    assert X.commit.__get__(None) is X.commit


@pytest.mark.asyncio
async def test_done_future():
    assert await done_future() is None
    assert await done_future(10) == 10


def callable():
    return 'sync'


async def async_callable():
    return 'async'


@pytest.mark.asyncio
@pytest.mark.parametrize('input,expected', [
    (callable, 'sync'),
    (async_callable, 'async'),
])
async def test_maybe_async(input, expected):
    assert await maybe_async(input()) == expected


async def test_maybe_cancel(loop):
    assert not maybe_cancel(None)
    future = loop.create_future()
    assert maybe_cancel(future)


class test_StampedeWrapper:

    @pytest.mark.asyncio
    async def test_concurrent(self):
        t = Mock()

        async def wrapped():
            await asyncio.sleep(0.5)
            return t()

        x = StampedeWrapper(wrapped)

        async def caller():
            return await x()

        assert all(
            ret is t.return_value
            for ret in await asyncio.gather(*[caller() for i in range(10)]))

        t.assert_called_once_with()

    @pytest.mark.asyncio
    async def test_sequential(self):
        t = Mock()

        async def wrapped():
            return t()

        x = StampedeWrapper(wrapped)

        for _ in range(10):
            assert await x() is t.return_value

        assert t.call_count == 10

    @pytest.mark.asyncio
    async def test_raises_cancel(self):

        async def wrapped():
            raise asyncio.CancelledError()

        x = StampedeWrapper(wrapped)

        with pytest.raises(asyncio.CancelledError):
            await x()

    @pytest.mark.asyncio
    async def test_already_done(self):

        async def wrapped():
            pass

        x = StampedeWrapper(wrapped)
        x.fut = done_future('foo')

        assert await x() == 'foo'
