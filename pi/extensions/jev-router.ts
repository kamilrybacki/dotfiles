/**
 * Jev router over the free models of the homelab LiteLLM (provider `litellm-free`).
 *
 * Registers `jev/free`. On every user message the Jev classifier rates how demanding the request
 * is (trivial / standard / complex) and the router picks the first model of that tier's chain.
 * Continuations of the same turn stay on the chosen model, so the prompt cache holds. A failed
 * request (quota, 429, 413, timeout) retries on the next model of the chain that has not failed yet.
 *
 * Jev needs TypeSafe credentials (TYPESAFE_API_KEY or an auth.json `typesafe` entry). Without them,
 * or when Jev errors, every message goes to the `standard` tier. Only the first 4000 characters of
 * the last user message are sent to Jev.
 *
 * Usage: pi --model jev/free   (extension auto-loads from ~/.pi/agent/extensions)
 */

import type { Message } from "@earendil-works/pi-ai";
import type { ExtensionAPI, ExtensionContext, ModelRoute, ModelRouteRequest } from "@earendil-works/pi-coding-agent";

const PROVIDER = "litellm-free";
const JEV_PROMPT_CHARS = 4_000;

type Tier = "trivial" | "standard" | "complex";

/** Ordered fallback chains, verified by tool-calling probes on 2026-10-28. */
const CHAINS: Record<Tier, readonly string[]> = {
	trivial: ["groq/qwen3-27b", "gemini/flash-lite", "mistral/ministral-8b", "openrouter/gemma-4-31b-free"],
	standard: ["gemini/flash-lite", "groq/qwen3-27b", "openrouter/gemma-4-31b-free", "mistral/ministral-8b"],
	complex: ["openrouter/gemma-4-31b-free", "gemini/flash-lite", "groq/qwen3-27b", "mistral/ministral-8b"],
};

/** Model for requests outside the agent loop, such as compaction summaries (1M context). */
const DIRECT_MODEL = "gemini/flash-lite";

interface RouterState {
	tier: Tier;
	model: string;
	/** Models that failed since the last user message. */
	failed: readonly string[];
}

type RouterRequest = ModelRouteRequest<RouterState>;

function routeTo(request: RouterRequest, ctx: ExtensionContext, id: string, state?: RouterState): ModelRoute<RouterState> {
	const model = ctx.modelRegistry.find(PROVIDER, id);
	if (!model) throw new Error(`Model ${PROVIDER}/${id} is not in models.json`);
	return { model, thinkingLevel: request.thinkingLevel, state };
}

function lastUserText(messages: readonly Message[]): string {
	const content = messages.filter((message) => message.role === "user").at(-1)?.content ?? "";
	if (typeof content === "string") return content;
	return content.flatMap((block) => (block.type === "text" ? [block.text] : [])).join("\n");
}

async function classifyTier(request: RouterRequest, ctx: ExtensionContext): Promise<Tier> {
	const jev = ctx.modelRegistry.findOfType("classifier", "typesafe", "jev-latest");
	if (!jev) return "standard";
	try {
		const result = await ctx.modelRegistry.classify(
			jev,
			{
				state: { prompt: lastUserText(request.messages).slice(0, JEV_PROMPT_CHARS) },
				questions: {
					tier: {
						type: "choice",
						instructions: "How demanding is the request in `prompt` for a coding agent?",
						criteria: {
							trivial: "Chit-chat, a one-line answer, or a lookup needing no reasoning",
							standard: "Ordinary coding: small features, fixes, explanations, reviews",
							complex: "Subtle design, multi-file changes, or hard debugging",
							other: "None of the above",
						},
					},
				},
			},
			{ signal: request.signal },
		);
		const answer = result.stopReason === "stop" ? result.answers.tier : undefined;
		if (answer?.type !== "choice") return "standard";
		const p = answer.probabilities;
		if ((p.complex ?? 0) >= 0.5) return "complex";
		if ((p.trivial ?? 0) >= 0.6) return "trivial";
		return "standard";
	} catch {
		return "standard";
	}
}

function nextInChain(tier: Tier, failed: readonly string[]): string {
	const next = CHAINS[tier].find((id) => !failed.includes(id));
	if (!next) throw new Error(`All free models of tier "${tier}" failed: ${failed.join(", ")}`);
	return next;
}

export default function (pi: ExtensionAPI) {
	pi.registerVirtualModel<RouterState>({
		provider: "jev",
		id: "free",
		name: "Free models (Jev router)",
		contextWindow: 131_072,
		maxTokens: 8_192,
		async route(request, ctx) {
			if (request.reason === "direct") return routeTo(request, ctx, DIRECT_MODEL);
			const state = request.state;

			if (request.reason === "retry" && state) {
				const failedId = request.failed?.model.id ?? state.model;
				const failed = [...state.failed, failedId];
				const model = nextInChain(state.tier, failed);
				return routeTo(request, ctx, model, { tier: state.tier, model, failed });
			}

			if (request.reason === "user" || !state) {
				const tier = await classifyTier(request, ctx);
				const model = CHAINS[tier][0];
				return routeTo(request, ctx, model, { tier, model, failed: [] });
			}

			return routeTo(request, ctx, state.model);
		},
	});
}
