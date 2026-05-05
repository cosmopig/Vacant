"""Spawn (D1-D5) tests. Each path has at least one named test."""

from __future__ import annotations

import pytest

from vacant.core.crypto import SigningKey, VerifyKey, keygen
from vacant.core.types import (
    BehaviorBundle,
    Logbook,
    ResidentForm,
    SubstrateSpec,
    VacantId,
    VacantState,
)
from vacant.runtime.errors import ConsentError, SpawnError
from vacant.runtime.spawn import (
    BIRTH_KIND,
    SPAWN_KIND,
    consent,
    make_d4_consent,
    spawn_capability_fork,
    spawn_clone_with_mutation,
    spawn_cross_substrate_respawn,
    spawn_lineage_merge,
    spawn_subagent_bud,
)


def _make_parent(
    *,
    state: VacantState = VacantState.ACTIVE,
    tools: list[str] | None = None,
    substrates: list[str] | None = None,
) -> tuple[ResidentForm, SigningKey, VerifyKey]:
    sk, vk = keygen()
    vid = VacantId.from_verify_key(vk)
    bundle = BehaviorBundle(
        system_prompt="be honest",
        policy_dsl="rule: do_no_harm",
        tool_whitelist=tools if tools is not None else ["search", "translate"],
    )
    spec = SubstrateSpec(
        allowed_substrates=substrates if substrates is not None else ["claude-sonnet-4-6"]
    )
    lb = Logbook()
    lb.append("genesis", {"name": "parent"}, sk)
    return (
        ResidentForm(
            identity=vid,
            logbook=lb,
            behavior_bundle=bundle,
            substrate_spec=spec,
            runtime_state=state,
        ),
        sk,
        vk,
    )


def _last_entry(form: ResidentForm) -> dict[str, object]:
    return dict(form.logbook.entries[-1].payload)


# --- D1 -------------------------------------------------------------------


def test_d1_clone_with_mutation_basics() -> None:
    parent, psk, _ = _make_parent()
    res = spawn_clone_with_mutation(parent, psk, policy_mutation="rule: be_concise")
    child = res.child
    assert res.path == "D1"
    assert child.parent_id == parent.identity
    assert child.runtime_state == VacantState.ACTIVE
    assert "be_concise" in child.behavior_bundle.policy_dsl
    assert child.behavior_bundle.tool_whitelist == parent.behavior_bundle.tool_whitelist
    # parent + child logbooks updated
    assert _last_entry(parent)["child_id"] == child.identity.hex()
    assert parent.logbook.entries[-1].kind == SPAWN_KIND
    assert child.logbook.entries[0].kind == BIRTH_KIND
    assert child.logbook.entries[0].payload["path"] == "D1"
    # Both chains verify with their respective keys
    assert parent.logbook.verify_chain(parent.identity.verify_key()) is True
    assert child.logbook.verify_chain(child.identity.verify_key()) is True
    assert child.verify_self() is True


def test_d1_requires_nonempty_mutation() -> None:
    parent, psk, _ = _make_parent()
    with pytest.raises(SpawnError):
        spawn_clone_with_mutation(parent, psk, policy_mutation="   ")


def test_spawn_rejects_non_runnable_parent() -> None:
    parent, psk, _ = _make_parent(state=VacantState.HIBERNATING)
    with pytest.raises(SpawnError):
        spawn_clone_with_mutation(parent, psk, policy_mutation="x")


# --- D2 -------------------------------------------------------------------


def test_d2_subagent_bud_is_local_with_narrowed_tools() -> None:
    parent, psk, _ = _make_parent(tools=["search", "translate", "exec"])
    res = spawn_subagent_bud(parent, psk, narrowed_tools=["search"])
    child = res.child
    assert res.path == "D2"
    assert child.runtime_state == VacantState.LOCAL
    assert child.behavior_bundle.tool_whitelist == ["search"]
    assert parent.logbook.entries[-1].payload["closed_child"] is True


def test_d2_rejects_extra_tools_outside_parent_set() -> None:
    parent, psk, _ = _make_parent(tools=["search"])
    with pytest.raises(SpawnError):
        spawn_subagent_bud(parent, psk, narrowed_tools=["search", "exec"])


# --- D3 -------------------------------------------------------------------


def test_d3_capability_fork_changes_capability_and_prompt() -> None:
    parent, psk, _ = _make_parent()
    res = spawn_capability_fork(
        parent,
        psk,
        new_capability_text="legal-research-zh",
        new_system_prompt="你是一名法律研究助理",
    )
    child = res.child
    assert res.path == "D3"
    assert child.behavior_bundle.system_prompt == "你是一名法律研究助理"
    birth = child.logbook.entries[0]
    assert birth.payload["new_capability_text"] == "legal-research-zh"


def test_d3_requires_nonempty_capability_and_prompt() -> None:
    parent, psk, _ = _make_parent()
    with pytest.raises(SpawnError):
        spawn_capability_fork(parent, psk, new_capability_text="", new_system_prompt="x")
    with pytest.raises(SpawnError):
        spawn_capability_fork(parent, psk, new_capability_text="x", new_system_prompt="")


# --- D4 -------------------------------------------------------------------


def test_d4_lineage_merge_combines_two_parents_with_consent() -> None:
    parent_a, psk_a, _ = _make_parent(tools=["search"])
    parent_b, psk_b, _ = _make_parent(tools=["translate", "exec"])
    token = make_d4_consent(parent_b, psk_b)
    res = spawn_lineage_merge(
        parent_a,
        psk_a,
        parent_b,
        token,
        merged_system_prompt="combined",
    )
    child = res.child
    assert res.path == "D4"
    assert child.parent_id == parent_a.identity
    assert sorted(child.behavior_bundle.tool_whitelist) == ["exec", "search", "translate"]
    birth = child.logbook.entries[0]
    assert birth.payload["secondary_parent_id"] == parent_b.identity.hex()


def test_d4_rejects_missing_consent() -> None:
    parent_a, psk_a, _ = _make_parent()
    parent_b, _psk_b, _ = _make_parent()
    bogus = consent(parent_b.identity, psk_a, intent="vacant:spawn:D4:lineage_merge")
    with pytest.raises(ConsentError):
        spawn_lineage_merge(
            parent_a,
            psk_a,
            parent_b,
            bogus,
            merged_system_prompt="x",
        )


def test_d4_rejects_wrong_intent() -> None:
    parent_a, psk_a, _ = _make_parent()
    parent_b, psk_b, _ = _make_parent()
    bad_intent = consent(parent_b.identity, psk_b, intent="something else")
    with pytest.raises(ConsentError):
        spawn_lineage_merge(parent_a, psk_a, parent_b, bad_intent, merged_system_prompt="x")


def test_d4_rejects_consent_for_wrong_parent() -> None:
    parent_a, psk_a, _ = _make_parent()
    parent_b, _, _ = _make_parent()
    parent_c, psk_c, _ = _make_parent()
    token_c = make_d4_consent(parent_c, psk_c)
    with pytest.raises(ConsentError):
        spawn_lineage_merge(parent_a, psk_a, parent_b, token_c, merged_system_prompt="x")


def test_d4_rejects_same_parent_twice() -> None:
    parent_a, psk_a, _ = _make_parent()
    token = make_d4_consent(parent_a, psk_a)
    with pytest.raises(SpawnError):
        spawn_lineage_merge(parent_a, psk_a, parent_a, token, merged_system_prompt="x")


# --- D5 -------------------------------------------------------------------


def test_d5_cross_substrate_respawn_preserves_bundle() -> None:
    parent, psk, _ = _make_parent(substrates=["claude-sonnet-4-6"])
    new_spec = SubstrateSpec(allowed_substrates=["qwen-2.5-72b"])
    res = spawn_cross_substrate_respawn(parent, psk, new_substrate_spec=new_spec)
    child = res.child
    assert res.path == "D5"
    assert child.behavior_bundle == parent.behavior_bundle
    assert child.substrate_spec.allowed_substrates == ["qwen-2.5-72b"]


def test_d5_rejects_identical_substrate_spec() -> None:
    parent, psk, _ = _make_parent(substrates=["claude-sonnet-4-6"])
    same = SubstrateSpec(allowed_substrates=["claude-sonnet-4-6"])
    with pytest.raises(SpawnError):
        spawn_cross_substrate_respawn(parent, psk, new_substrate_spec=same)


def test_d5_rejects_empty_substrate_spec() -> None:
    parent, psk, _ = _make_parent()
    empty = SubstrateSpec()
    with pytest.raises(SpawnError):
        spawn_cross_substrate_respawn(parent, psk, new_substrate_spec=empty)


# --- common ---------------------------------------------------------------


def test_each_spawn_path_yields_distinct_keypair() -> None:
    parent, psk, pvk = _make_parent()
    r1 = spawn_clone_with_mutation(parent, psk, policy_mutation="x")
    r2 = spawn_clone_with_mutation(parent, psk, policy_mutation="y")
    assert r1.child.identity != r2.child.identity
    assert r1.child.identity != parent.identity
    assert bytes(r1.child.identity.verify_key()) != bytes(pvk)


def test_consent_helper_round_trip() -> None:
    sk, vk = keygen()
    vid = VacantId.from_verify_key(vk)
    token = consent(vid, sk, intent="hello")
    assert token.parent_id == vid
    assert token.intent == "hello"
    assert len(token.signature) == 64
