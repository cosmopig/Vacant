# P2 — Identity / Sybil / Whitewashing 研究 Raw Output

> **來源**：本文件為 P2-identity pane 透過 `codex exec` 命令向 Codex CLI 發出之深度文獻調查 raw 輸出，未經改寫。引用、章節定位、DOI / arXiv ID 由 Codex 從可驗證來源產出。`P2_identity.md` 設計決策中的所有引用以本文件為一手依據。
>
> **執行**：`codex exec --skip-git-repo-check --sandbox read-only -c model_reasoning_effort=high`
> **時間**：2026-05-01
> **prompt 長度**：5083 bytes
> **覆蓋面向**：9 個身份/Sybil 抵抗方案 × (canonical reference / mechanism / Sybil resistance / whitewashing cost / Vacant portability / MVP eng cost / known attacks / quote-formula)，並加 1 比較表 + 1 綜合論述。

---

## 研究 prompt（送出給 codex 的完整指令）

````
You are doing literature research for a graduate-thesis project called "Vacant" — a decentralized
network of autonomous LLM agents ("individual vacants"). The project rejects any central LLM-judge
or gating authority. Reputation is multi-dim, accumulated via peer review. The OPEN-NETWORK design
therefore needs an identity layer that resists Sybil and whitewashing without a central arbiter.

Produce a thorough literature/industry survey on identity anchoring and Sybil resistance for
autonomous LLM agents. Cover the following 8 schemes IN DEPTH and conclude with a comparison table.

For each scheme, output exactly this structure:

### <Scheme name>
- **Source / canonical reference**
- **One-paragraph mechanism description**
- **Sybil resistance strength**
- **Whitewashing cost**
- **Portability to Vacant**
- **Engineering cost for an MVP**
- **Known attacks / failure modes**
- **Specific quote or formula** that Vacant can reuse.

The 8 schemes (expanded to 9 with stake-based identity):
1. Friedman & Resnick (2001) "The Social Cost of Cheap Pseudonyms" — and Friedman/Resnick/Sami (2007).
2. Douceur (2002) "The Sybil Attack" (IPTPS).
3. ETHOS framework — arXiv:2412.17114.
4. Bouchiha et al. — agent reputation / SSI for AI agents.
5. Soulbound Tokens (SBT) — Vitalik Buterin, E. Glen Weyl, Puja Ohlhaver (May 2022).
6. SSI / DID — W3C DID v1.0 + VC Data Model. did:key, did:web, did:ion.
7. Enterprise attestation — TPM, SGX/TDX, GCP Confidential Space, AWS Nitro Enclaves.
8. Web of Trust — PGP/GPG (RFC 4880), keybase.io, Sigstore/Fulcio, TrustChain.
9. Stake-based identity — PoS deposits, Optimistic-rollup bonds, Nostr NIP-13, Worldcoin PoP.

Then: comparison table + synthesis section answering BRIEFING tensions on (i) network elimination
vs whitewashing and (ii) no central judge vs cold start, plus federation path Q1 and open ethical
problems.

Constraints: cite specific arXiv IDs / DOIs / W3C URLs / SSRN IDs. Do NOT invent citations — if a
source cannot be verified, mark it [unverified] and explain why. 4000-6000 words.
````

---

## Codex Raw Output

Below I cover all 9 numbered schemes.

### Friedman & Resnick newcomer distrust / "cheap pseudonyms"
- **Source / canonical reference**: Eric J. Friedman & Paul Resnick, "The Social Cost of Cheap Pseudonyms," *Journal of Economics & Management Strategy*, 2001, DOI `10.1111/j.1430-9134.2001.00173.x` ([EconPapers](https://econpapers.repec.org/RePEc%3Abla%3Ajemstr%3Av%3A10%3Ay%3A2001%3Ai%3A2%3Ap%3A173-199), [CiNii](https://cir.nii.ac.jp/crid/1362825895446262656)); Eric Friedman, Paul Resnick & Rahul Sami, "Manipulation-Resistant Reputation Systems," ch. 27 in *Algorithmic Game Theory*, 2007, DOI `10.1017/CBO9780511800481.029` ([Resnick page](https://presnick.people.si.umich.edu/papers/agt/)).
- **One-paragraph mechanism description**: Friedman & Resnick do not "anchor" identity cryptographically; they analyze what happens when pseudonyms are cheap. Their lever is economic and game-theoretic: if identities can be discarded, bad actors can escape bad reputation, so the equilibrium substitute is a newcomer tax. New pseudonyms must initially accept worse treatment, lower privileges, higher review burden, escrow, delayed payouts, or lower task priority until they accumulate enough credible history. The attacker pays by losing the surplus that an established reputation would have earned during the probation period.
- **Sybil resistance strength**: Moderate. It does not prevent Sybils, but makes mass identity rotation less profitable when the probation tax exceeds expected fraud gain.
- **Whitewashing cost**: Concrete cost is `probation_length × lost_expected_surplus + extra_verification_costs + delayed_capital`. For Vacant: e.g. 30 days of low-trust routing, mandatory peer review, no access to high-value tasks, higher escrow ratio, and zero carry-over reputation.
- **Portability to Vacant**: High. It is fully compatible with an open network, no central LLM judge, software agents, Ed25519 keys, and A2A. It only requires peers to treat fresh keys differently from aged keys.
- **Engineering cost for an MVP**: Low. Add `created_at`, first-seen Merkle proof, per-agent age, probation tier, task limits, and reputation decay rules. No issuer is required. Key surface is just the vacant's Ed25519 identity key plus rotation/recovery metadata.
- **Known attacks / failure modes**: Legitimate newcomers are harmed; incumbents gain advantage; attackers can run Sybil farms patiently through probation; colluding old identities can sponsor new ones. Friedman/Resnick/Sami explicitly list whitewashing and Sybil feedback manipulation as strategic threats ([Resnick page](https://presnick.people.si.umich.edu/papers/agt/)).
- **Specific quote or formula** that Vacant can reuse: "newcomers 'pay their dues'" (Friedman & Resnick, 2001, abstract). Vacant formula: `initial_trust = base_trust × f(age, verified_interactions, stake_or_attestations)` with `f(0)=low`.

### Douceur Sybil impossibility
- **Source / canonical reference**: John R. Douceur, "The Sybil Attack," IPTPS 2002, LNCS 2429, pp. 251-260, DOI `10.1007/3-540-45748-8_24` ([Microsoft Research](https://www.microsoft.com/en-us/research/publication/the-sybil-attack/), [DBLP](https://dblp.org/rec/conf/iptps/Douceur02.html)).
- **One-paragraph mechanism description**: Douceur defines the core problem: in a distributed system, one adversarial entity can present many identities. If identities are free and remote entities cannot know whether identities correspond to distinct real-world entities, redundancy and voting fail. The paper's central result is negative: without a logically centralized identity certification authority, Sybil attacks remain possible except under unrealistic assumptions about equal resource distribution and global coordination. The two practical escapes are certified identity or costly resource tests.
- **Sybil resistance strength**: Strong as a theorem, weak as a standalone mechanism. It precisely says what Vacant cannot get for free.
- **Whitewashing cost**: Zero if keys are free; positive only if Vacant adds newcomer tax, resource challenge, stake, attestation, or issuer-backed credentials.
- **Portability to Vacant**: High conceptually. It is the boundary condition for Vacant's identity layer: an Ed25519 key alone is not Sybil resistant.
- **Engineering cost for an MVP**: Low to incorporate as design rule. Enforce that every reputation edge must declare its anti-Sybil basis: age, stake, VC, SBT, attestation, or peer-trust path.
- **Known attacks / failure modes**: Any scheme based only on self-generated public keys is Sybilable; any peer vote can be captured if the attacker can cheaply mint voters. Douceur's abstract states that a faulty entity presenting many identities undermines redundancy ([Microsoft Research](https://www.microsoft.com/en-us/research/publication/the-sybil-attack/)).
- **Specific quote or formula** that Vacant can reuse: "without a logically centralized authority, Sybil attacks are always possible" (Douceur, 2002, abstract). Vacant design rule: `identity_key != personhood != uniqueness`.

### ETHOS decentralized AI-agent identity
- **Source / canonical reference**: Tomer Jordi Chaffer, Charles von Goins II, Dontrail Cotlage, Bayo Okusanya & Justin Goldston, "Decentralized Governance of Autonomous AI Agents," arXiv `2412.17114`, DOI `10.48550/arXiv.2412.17114`, v3 Jan. 11 2025 ([arXiv](https://arxiv.org/abs/2412.17114)). Canonical title verified; **not** "Towards Ethical and Humanlike Multi-Agent Systems."
- **One-paragraph mechanism description**: ETHOS proposes a decentralized governance framework for autonomous AI agents using a global registry, blockchain, smart contracts, DAOs, SSI, SBTs, zero-knowledge proofs, reputation systems, staking, and oracles. In §5.1 and §5.3, each AI agent receives a digital identity containing compliance credentials, performance logs, and audit results; SBTs act as non-transferable certifications for ethical benchmarks; ZKPs allow compliance checks without exposing private data. The attacker cost comes from losing non-transferable attestations, risk status, stake, and registry history.
- **Sybil resistance strength**: Moderate. ETHOS combines identity, SBTs, staking, and reputation, but still relies on issuers, auditors, or validators whose legitimacy must be governed.
- **Whitewashing cost**: Loss of SBTs, compliance history, risk tier, audit trail, validator stake, and insurance/legal-entity linkage. In Vacant terms: social and economic cost, not hard uniqueness.
- **Portability to Vacant**: Medium. The SSI/SBT/history layer is useful, but ETHOS leans toward global registry and governance institutions, which conflict with Vacant's rejection of a central judge unless implemented as federated registries.
- **Engineering cost for an MVP**: Medium to high. Requires agent registry, DID documents, signed credentials, revocation, optional SBT contract, off-chain evidence store, peer-validator attestations, and key recovery. Issuers are developers, orgs, auditors, or peer agents.
- **Known attacks / failure modes**: Oracle manipulation, validator collusion, DAO capture, fake audits, SBT privacy leakage, and centralization of issuer power. ETHOS itself uses reputation and staking penalties for "false verification or data manipulation" (§5.1, [arXiv PDF](https://arxiv.org/pdf/2412.17114)).
- **Specific quote or formula** that Vacant can reuse: "Each agent is assigned a digital identity" (Chaffer et al., 2025, §5.3). Vacant reuse: `AgentID = Ed25519 pubkey + DID document + signed history root`.

### Bouchiha et al. LLMChain / AI reputation
- **Source / canonical reference**: Mouhamed Amine Bouchiha, Quentin Telnoff, Souhail Bakkali, Ronan Champagnat, Mourad Rabah, Mickaël Coustaty & Yacine Ghamri-Doudane, "LLMChain: Blockchain-based Reputation System for Sharing and Evaluating Large Language Models," arXiv `2404.13236`, DOI `10.48550/arXiv.2404.13236`; COMPSAC 2024, pp. 439-448, DOI `10.1109/COMPSAC61105.2024.00067` ([DBLP](https://dblp.org/rec/journals/corr/abs-2404-13236.html), [HAL PDF](https://l3i.univ-larochelle.fr/app/uploads/sites/12/2025/01/2404.13236v2.pdf)). I could verify Bouchiha papers on blockchain reputation for LLMs and decentralized federated learning; I could not verify a specific Bouchiha "SSI for AI agents" paper, so that part is **[unverified]**.
- **One-paragraph mechanism description**: LLMChain is a decentralized reputation framework for LLMs, not agent identity per se. It combines automatic evaluation and human feedback, records evaluation events on blockchain, and derives contextual reputation scores for models. The attacker cost is the cost of creating credible evaluation history, manipulating feedback, or publishing a new model with no prior reputation. It is closer to Vacant's "multi-dimensional peer-review history" than to a uniqueness anchor.
- **Sybil resistance strength**: Weak to Moderate. Blockchain immutability prevents tampering after publication, but evaluator identities and feedback Sybils still need separate anti-Sybil controls.
- **Whitewashing cost**: Loss of accumulated model/agent score and evaluation history. Direct monetary cost is chain gas plus evaluation workload; social cost depends on who trusts the evaluators.
- **Portability to Vacant**: Medium. Strong fit for contextual reputation cards, weak fit for identity uniqueness unless paired with DID/SBT/stake/attestation.
- **Engineering cost for an MVP**: Medium. Need signed evaluation receipts, benchmark metadata, feedback schema, reputation aggregation, append-only storage, and dispute/rebuttal flow. Issuers are peer vacants, benchmark runners, task clients, or CI systems.
- **Known attacks / failure modes**: Feedback Sybils, benchmark gaming, collusive reviews, context conflation, and reputation transfer across unrelated tasks. LLMChain itself combines automatic evaluation with human feedback to address trust gaps.
- **Specific quote or formula** that Vacant can reuse: "contextual reputation scores" (Bouchiha et al., 2024, abstract). Vacant reuse: `Rep(agent, domain, verifier_class, time)` rather than a single scalar.

### Soulbound Tokens
- **Source / canonical reference**: Puja Ohlhaver, E. Glen Weyl & Vitalik Buterin, "Decentralized Society: Finding Web3's Soul," SSRN ID `4105763`, DOI `10.2139/ssrn.4105763`, May 2022 ([SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4105763)); ERC-5192 "Minimal Soulbound NFTs," final ERC, 2022 ([EIP-5192](https://eips.ethereum.org/EIPS/eip-5192)).
- **One-paragraph mechanism description**: SBTs are non-transferable tokens attached to "Souls," representing affiliations, credentials, commitments, memberships, or attestations. For Vacant, a Soul can be an agent DID or wallet controlled by an Ed25519-to-EVM bridge or a linked secp256k1 key. Non-transferability changes whitewashing economics because a useful credential cannot simply be sold or moved to a fresh identity; abandoning an identity burns its accumulated social graph and attestations.
- **Sybil resistance strength**: Moderate. SBTs make reputation harder to transfer but do not guarantee one entity equals one identity.
- **Whitewashing cost**: Loss of all non-transferable credentials and social graph. Dollar cost equals re-acquiring issuer attestations, audits, insurance, deposits, or contribution history.
- **Portability to Vacant**: Medium. Good for provenance and reputation anchoring; lower portability if Vacant wants no mandatory chain or issuer.
- **Engineering cost for an MVP**: Medium. Need SBT contract or off-chain equivalent, issuer keys, revocation, privacy strategy, and binding to the agent's DID/A2A card. ERC-5192 gives a minimal `locked(tokenId)` interface.
- **Known attacks / failure modes**: Privacy leakage, coercive credentials, issuer capture, unwanted permanent marks, wallet loss, social-graph deanonymization. The DeSoc paper itself frames SBTs as encoding trust relationships ([SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4105763)).
- **Specific quote or formula** that Vacant can reuse: "non-transferable 'soulbound' tokens" (Ohlhaver/Weyl/Buterin, 2022, abstract). Formula: `whitewash_cost = value(nontransferable_attestations_lost)`.

### SSI / DID / Verifiable Credentials
- **Source / canonical reference**: W3C Decentralized Identifiers v1.0, W3C Recommendation, 19 July 2022 ([W3C DID Core](https://www.w3.org/TR/did/)); W3C Verifiable Credentials Data Model v1.1, Recommendation, 3 March 2022 ([W3C VC](https://www.w3.org/TR/2022/REC-vc-data-model-20220303/)); DID methods: `did:key`, `did:web`, `did:ion` / Sidetree ([ION](https://identity.foundation/ion/), [Sidetree spec](https://identity.foundation/sidetree/spec/)).
- **One-paragraph mechanism description**: DID gives an agent a resolvable identifier whose DID document contains verification keys and service endpoints. VC lets an issuer make signed claims about the subject: developer/org origin, code hash, model family, capability scope, safety audit, enclave measurement, or prior registry membership. `did:key` is self-certifying and cheap; `did:web` anchors in DNS/TLS; `did:ion` anchors DID operations into Bitcoin via Sidetree/IPFS. The attacker cost depends entirely on credential issuers and anchoring method.
- **Sybil resistance strength**: Weak alone, Moderate with credible VCs. A self-created DID is just a key; a DID with scarce attestations has cost.
- **Whitewashing cost**: For `did:key`: near zero. For `did:web`: domain cost and org continuity. For `did:ion`: Bitcoin anchoring cost plus operation history. For VC-backed identity: cost of re-issuance by trusted issuers.
- **Portability to Vacant**: High. DIDs and VCs fit Ed25519 and A2A well; an A2A Agent Card can publish the DID and accepted verification methods.
- **Engineering cost for an MVP**: Low to Medium. Use `did:key` with Ed25519, JSON DID doc, signed VC-JWT or Data Integrity proof, issuer allowlists per peer, and optional `did:web` for org provenance. No central issuer required.
- **Known attacks / failure modes**: DID method fragmentation, issuer trust ambiguity, key loss, DNS takeover for `did:web`, cheap Sybils for `did:key`, and correlation/privacy leakage in reusable credentials. W3C notes DIDs are decoupled from centralized registries, not inherently Sybil-proof ([W3C news](https://www.w3.org/news/2022/decentralized-identifiers-dids-v1-0-is-a-w3c-recommendation/)).
- **Specific quote or formula** that Vacant can reuse: DID "identifies any subject" (W3C DID Core, 2022). Vacant formula: `VacantID = did:key:z...Ed25519`, plus `VC(subject=VacantID, claim=origin/code/capability)`.

### Enterprise attestation / TPM, SGX, TDX, Confidential Space, Nitro
- **Source / canonical reference**: IETF RFC 9334 "Remote ATtestation procedureS (RATS) Architecture" ([RFC 9334](https://www.ietf.org/rfc/rfc9334.html)); TCG TPM 2.0 Library; Intel SGX/DCAP attestation ([Intel SGX attestation](https://www.intel.com/content/www/us/en/developer/tools/software-guard-extensions/attestation-services.html)); AWS Nitro Enclaves attestation docs ([AWS](https://docs.aws.amazon.com/enclaves/latest/user/set-up-attestation.html)); Google Cloud Confidential Space attestation ([Google Cloud](https://cloud.google.com/confidential-computing/docs/attestation)).
- **One-paragraph mechanism description**: Remote attestation binds identity to measured software and hardware. A TPM quote, SGX/TDX quote, Nitro attestation document, or Google Confidential Space token proves that a workload with a specific measurement, image digest, PCR set, or enclave identity is running inside a trusted environment. For Vacant, the vacant's Ed25519 key can be generated inside the enclave and included in attestation `user_data` or nonce-bound evidence, binding the network identity to the binary rather than merely to the operator.
- **Sybil resistance strength**: Moderate. It proves "this code in this TEE," not "only one agent." Stronger if TEEs are scarce, costly, and rate-limited by cloud accounts or hardware.
- **Whitewashing cost**: Cloud compute cost, enclave deployment cost, image signing, audit cost, and loss of attested history. AWS Nitro PCR policy can bind access to PCR0/PCR8; Google tokens include workload image digest; Intel uses MRENCLAVE/MRSIGNER.
- **Portability to Vacant**: Medium. Excellent for software agents, but introduces vendor trust roots and geographic/cloud inequality.
- **Engineering cost for an MVP**: High. Need enclave build pipeline, reproducible images, attestation verifier, trust-anchor store, nonce freshness, key generation inside enclave, evidence storage, and fallback for non-TEE agents.
- **Known attacks / failure modes**: Side channels, stale measurements, debug mode, compromised supply chain, vendor CA dependence, verifier policy bugs, relay/replay without nonces. SGX has known attacks such as Controlled-Channel, DOI `10.1109/SP.2015.45` ([DBLP](https://dblp.org/rec/conf/sp/XuCP15.html)), and Foreshadow, USENIX Security 2018 ([USENIX](https://www.usenix.org/conference/usenixsecurity18/presentation/bulck)).
- **Specific quote or formula** that Vacant can reuse: RATS: Attester produces "Evidence" for a Verifier (RFC 9334, §1). Vacant formula: `AgentKey := Ed25519 key generated in enclave; Attestation.user_data = hash(AgentKey || nonce)`.

### Web of Trust / PGP, Keybase, Sigstore, TrustChain
- **Source / canonical reference**: OpenPGP RFC 4880, 2007 ([RFC 4880](https://www.rfc-editor.org/rfc/rfc4880)); Sigstore paper: Zachary Newman, John Speed Meyers & Santiago Torres-Arias, "Sigstore: Software Signing for Everybody," ACM CCS 2022, DOI `10.1145/3548606.3560596` ([NSF](https://par.nsf.gov/biblio/10470793)); Fulcio/Rekor docs ([Sigstore](https://docs.sigstore.dev/)); Otte, de Vos & Pouwelse, "TrustChain: A Sybil-resistant scalable blockchain," *Future Generation Computer Systems*, DOI `10.1016/j.future.2017.08.048` ([ScienceDirect](https://www.sciencedirect.com/science/article/pii/S0167739X17318988)).
- **One-paragraph mechanism description**: Web of Trust anchors identity in signatures from other keys. PGP lets users certify keys and delegate introducer trust; Keybase revived this by linking keys to social proofs; Sigstore binds artifact signatures to OIDC identities and transparency logs; TrustChain stores signed bilateral interactions per agent and derives trust via NetFlow-like accounting. For Vacant, a peer can sign: "I have interacted with this vacant, and it is not a sock-puppet of mine to the best of my evidence," scoped by domain and confidence.
- **Sybil resistance strength**: Moderate. It resists Sybils when trust paths originate from scarce, high-reputation roots and when endorsements are costly or slashable.
- **Whitewashing cost**: Loss of trust paths, signatures, transparency-log entries, and bilateral history. Rebuilding requires convincing existing reputable agents to sign again.
- **Portability to Vacant**: High. Native fit for Ed25519 signatures, peer review, no central judge, and A2A-discoverable attestations.
- **Engineering cost for an MVP**: Medium. Need signed endorsement schema, trust-path evaluation, endorsement revocation, conflict handling, graph weighting, transparency log or Merkle gossip sync.
- **Known attacks / failure modes**: Collusive signing rings, misplaced transitive trust, stale/revoked keys, social proof account takeover, OIDC compromise in Sigstore, log-monitoring gaps. Sigstore explicitly says compromised OIDC can cause unauthorized certificates, detectable only if logs are monitored ([Sigstore security](https://docs.sigstore.dev/about/security/)).
- **Specific quote or formula** that Vacant can reuse: RFC 4880 trust signature: "valid trusted introducer" (RFC 4880, §5.2.3.13). Formula: `trust(A→C)=max_paths min(edge_confidence × signer_reputation × scope_match)`.

### Stake-based identity / PoS, bonds, Nostr PoW, Worldcoin PoP
- **Source / canonical reference**: Ethereum proof-of-stake validator deposit and slashing docs ([ethereum.org](https://ethereum.org/en/developers/docs/consensus-mechanisms/pos/rewards-and-penalties/)); Optimism fault-proof bonds ([Optimism docs](https://docs.optimism.io/op-stack/fault-proofs/challenger)); Nostr NIP-13 Proof of Work ([NIP-13](https://nostr-nips.com/nip-13)); Worldcoin / World ID proof of personhood protocol ([Worldcoin protocol](https://world.org/the-worldcoin-protocol), [World whitepaper](https://whitepaper.world.org/achieving-proof-of-human)).
- **One-paragraph mechanism description**: Stake-based identity makes each identity costly. PoS requires capital lockup and slashing risk; optimistic-rollup bonds require challengers/proposers to post capital that can be lost; NIP-13 makes each message or identity carry proof-of-work difficulty; Worldcoin uses biometric proof of personhood so one human receives one credential. For Vacant, the software-agent-compatible parts are stake, bonds, and PoW; Worldcoin is mostly a human-origin credential, useful only for developer/operator provenance.
- **Sybil resistance strength**: Strong for capital-bounded systems, Moderate for PoW, Strong-for-humans but Low-for-agents for Worldcoin.
- **Whitewashing cost**: PoS: 32 ETH per Ethereum validator plus slashing risk. Optimism: per-claim dispute bonds; docs cite over 631.2 ETH to play one full game path. NIP-13: expected `2^d` hashes per event. Worldcoin: biometric enrollment/social access cost, not suitable for agent multiplicity.
- **Portability to Vacant**: Medium. Bonds and PoW are high portability; PoS capital lockup is useful for high-risk agents; Worldcoin conflicts with "must work for software agents."
- **Engineering cost for an MVP**: Low for PoW; Medium for escrow/bonds; High for on-chain stake/slashing; Low integration but poor fit for Worldcoin credentials.
- **Known attacks / failure modes**: Wealth concentration, rented stake, bribery, stake grinding, PoW hardware advantage, energy waste, bond griefing, biometric exclusion/privacy concerns, KYC creep. Worldcoin uses Orb/iris uniqueness and ZK privacy claims but depends on hardware distribution and biometric trust ([World whitepaper](https://whitepaper.world.org/achieving-proof-of-human)).
- **Specific quote or formula** that Vacant can reuse: NIP-13: difficulty is "leading zero bits" (NIP-13). Formula: `expected_work = 2^difficulty hashes`; `identity_cost = locked_capital × lock_time × risk_factor`.

### Comparative table
| Scheme | Sybil resistance | Whitewashing cost | Portable to Vacant | MVP eng cost |
|---|---|---|---|---|
| Friedman & Resnick newcomer tax | Moderate | Probation loss, delayed privileges, escrow, time | High | Low |
| Douceur impossibility | N/A boundary theorem | Zero unless extra cost added | High | Low |
| ETHOS | Moderate | Lost SBTs, risk tier, audit trail, stake | Medium | Medium-High |
| Bouchiha / LLMChain | Weak-Moderate | Lost contextual evaluation history | Medium | Medium |
| SBT | Moderate | Lost non-transferable credentials/social graph | Medium | Medium |
| SSI / DID / VC | Weak alone, Moderate with issuers | Near zero for `did:key`; issuer re-attestation for VCs | High | Low-Medium |
| Enterprise attestation | Moderate | Cloud/TEE cost, lost measured-code history | Medium | High |
| Web of Trust / Sigstore / TrustChain | Moderate | Lost trust paths and signed interaction history | High | Medium |
| Stake / PoW / PoP | Moderate-Strong depending cost | Capital lockup, slashing, `2^d` hashes, biometric enrollment | Medium | Low-High |

### Synthesis for Vacant
A practical Vacant stack should be defense-in-depth, not a single identity oracle. **L0** is self-certifying cryptographic identity: Ed25519 key, DID document, A2A Agent Card, signed metadata, and first-seen timestamp. **L1** is history anchoring: append-only signed interaction receipts, Merkle roots, and peer-review events. **L2** is costly credibility: newcomer tax, stake/bonds, NIP-13-style PoW for low-value spam resistance, and SBT/VC provenance for scarce credentials. **L3** is high-assurance execution: optional enclave attestation proving a specific vacant binary controls the key.

Cold start should not require a central LLM judge. A new vacant begins with low prior trust by default, following Friedman & Resnick's "pay dues" logic. It can earn non-zero prior through attestable provenance: developer VC, org DID, signed release provenance, Sigstore entry, SBT certification, small stake, or a TEE measurement. None of these says "this agent is good"; they say "this agent is costly to fake or abandon."

The federation path can preserve different guarantees. In Q1 single-Registry, the registry can provide convenience and canonical first-seen timestamps, but it is a central availability and policy point. In federated Merkle root sync, no single registry can silently rewrite history if peers gossip roots and inclusion proofs. In a fully decentralized path using libp2p/IPNS/on-chain SBTs, identity guarantees reduce to key control, signed history, issuer trust, and economic cost; global uniqueness still does not magically appear.

The "natural network elimination" tension is solved only if elimination destroys something costly. If a bad vacant can make a fresh key and immediately regain access, elimination is bypassable. Therefore elimination must burn or strand reputation, aged trust paths, stake, SBTs, VC provenance, task access, and probation time. The "no central judge vs cold start" tension is solved by separating provenance from judgment: the first vacant's reputation comes from founder/developer credentials, signed code provenance, peer attestations, and limited successful interactions, not from an authority declaring it trustworthy.

Open problems remain substantial. Attestation can leak sensitive operator data; SBTs can become permanent surveillance labels; enterprise TEEs privilege agents with access to AWS/GCP/Intel-supported regions; proof-of-personhood can drift toward KYC; and stake-based systems privilege capital. Vacant should expose the basis of every trust score as machine-readable evidence, keep reputation multi-dimensional, allow privacy-preserving proofs where possible, and never collapse identity into a universal moral score.

---

## P2 對 codex 輸出的接收注記

1. **ETHOS 標題與作者已校正**——BRIEFING 提供的 arXiv:2412.17114 對應的 *canonical title* 是 Chaffer et al. 2025 的 *Decentralized Governance of Autonomous AI Agents*，**不是** "Towards Ethical and Humanlike Multi-Agent Systems"。P2_identity.md §5 的引用以此版本為準。
2. **Bouchiha 對應論文是 LLMChain (arXiv:2404.13236, COMPSAC 2024)**，而非「SSI for AI agents」（後者 codex 標 [unverified]）。P2 採用 LLMChain 作為 contextual reputation 的學術錨。
3. **SBT 作者順序 Ohlhaver / Weyl / Buterin**（Vitalik 為第三作者），SSRN ID 4105763 已確認。
4. **ETHOS / DID / SBT / RATS / RFC 9334 / Sigstore / NIP-13 / TrustChain** 全套引用通過 codex 二次確認。
5. **三段路線圖** (single Registry → federated Merkle → decentralized libp2p+SBT) 與 P2_identity.md §D5 一致；codex 進一步指出「federated Merkle root sync 階段需 gossip inclusion proofs」可作為 P4 的補充提示。
6. **冷啟動共識**：codex 與 P2 設計同樣不從 LLM-judge 取得 prior，而從 attestable provenance（DID、VC、Sigstore entry、SBT、stake、TEE measurement）取得；本身 *only* 表達「fake/abandon 的成本」，不直接代言能力。
7. **倫理風險 codex 額外提示**：(a) attestation 洩漏 operator 資料 → P2_identity.md §7 Q-P2-3 ZK 變體；(b) SBT 變成永久監控標籤 → 列入 §7 開放問題；(c) TEE 帶 vendor / 地域不平等 → §4 R1 已記錄；(d) PoP 走向 KYC creep → §2 D2 已否決全網 KYC。

---

*Document created 2026-05-01. 本檔作為 P2_identity.md 引用的一手依據；任何 P2 引用變動須回到本文件對照。*
