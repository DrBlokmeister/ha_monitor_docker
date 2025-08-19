import pytest

from custom_components.monitor_docker import async_migrate_entry
from custom_components.monitor_docker.const import CONF_CONTAINERS
from homeassistant.const import CONF_MONITORED_CONDITIONS


class MockEntry:
    def __init__(self, data, options=None, version=1):
        self.data = data
        self.options = options or {}
        self.version = version
        self.entry_id = "test"


class MockConfigEntries:
    def async_update_entry(self, entry, data=None, options=None):
        if data is not None:
            entry.data = data
        if options is not None:
            entry.options = options


class MockHass:
    def __init__(self):
        self.config_entries = MockConfigEntries()


@pytest.mark.asyncio
async def test_migrate_entry_moves_data_to_options():
    entry = MockEntry(
        {
            CONF_CONTAINERS: ["c1"],
            CONF_MONITORED_CONDITIONS: ["condition"],
            "other": 1,
        }
    )
    hass = MockHass()

    assert await async_migrate_entry(hass, entry)
    assert entry.version == 2
    assert CONF_CONTAINERS not in entry.data
    assert CONF_MONITORED_CONDITIONS not in entry.data
    assert entry.options[CONF_CONTAINERS] == ["c1"]
    assert entry.options[CONF_MONITORED_CONDITIONS] == ["condition"]
    assert entry.data["other"] == 1
