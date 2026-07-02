import { PUBLIC_API_BASE } from '$env/static/public';

const BASE = PUBLIC_API_BASE ?? 'http://localhost:8000';

export type EmotionProbs = Record<string, number>;

export interface InferResult {
	emotion_probs: EmotionProbs;
	valence: number;
	arousal: number;
	zone: string;
}

export interface Profile {
	age: number;
	sex: 'male' | 'female';
	height_cm: number;
	weight_kg: number;
	activity: string;
}

export interface FoodOut {
	id: string;
	name: string;
	source: string;
	calories: number | null;
	image_hint: string | null;
}

export interface MealOut {
	food: FoodOut;
	enms: number;
	m_macro: number;
	m_micro: number;
	satisfied_targets: string[];
}

export interface NNVData {
	zone: string;
	macro_targets: Record<string, number>;
	macro_weights: Record<string, number>;
	micro_targets: Record<string, number>;
	priority_micros: string[];
}

export interface RecommendRequest {
	zone: string;
	profile?: Profile;
	meal_type?: string; // breakfast|lunch|dinner|snack; omit for a flat 1/3 portion
}

export interface RecommendResult {
	meals: MealOut[];
	nnv: NNVData;
}

export interface Place {
	name: string;
	lat: number;
	lng: number;
	distance_m: number;
	address: string;
}

export interface RestaurantResult {
	places: Place[];
	disabled?: boolean;
}

export class ApiError extends Error {
	constructor(
		public status: number,
		message: string
	) {
		super(message);
		this.name = 'ApiError';
	}
}

async function asJson<T>(res: Response): Promise<T> {
	if (!res.ok) {
		let detail = res.statusText;
		try {
			const body = await res.json();
			detail = (body as { detail?: string }).detail ?? detail;
		} catch {
			/* non-JSON error body; keep statusText */
		}
		throw new ApiError(res.status, detail);
	}
	return (await res.json()) as T;
}

export async function recommend(req: RecommendRequest): Promise<RecommendResult> {
	const res = await fetch(`${BASE}/api/recommend`, {
		method: 'POST',
		headers: { 'content-type': 'application/json' },
		body: JSON.stringify(req)
	});
	return asJson<RecommendResult>(res);
}

export async function fetchFoods(): Promise<FoodOut[]> {
	const res = await fetch(`${BASE}/api/foods`);
	const body = await asJson<{ foods: FoodOut[] }>(res);
	return body.foods;
}

export async function fetchImages(food: string): Promise<string[]> {
	const res = await fetch(`${BASE}/api/images?food=${encodeURIComponent(food)}`);
	const body = await asJson<{ images: string[] }>(res);
	return body.images;
}

export async function fetchRestaurants(
	food: string,
	lat: number,
	lng: number
): Promise<RestaurantResult> {
	const qs = new URLSearchParams({ food, lat: String(lat), lng: String(lng) });
	const res = await fetch(`${BASE}/api/restaurants?${qs.toString()}`);
	return asJson<RestaurantResult>(res);
}

export interface RealtimeToken {
	provider: 'openai' | 'gemini';
	client_secret: string;
	model: string;
	voice: string;
	ws_url?: string;
	api_version?: string;
}

export async function fetchRealtimeToken(): Promise<RealtimeToken> {
	const res = await fetch(`${BASE}/api/realtime/token`, { method: 'POST' });
	return asJson<RealtimeToken>(res);
}

export interface VoiceConfig {
	provider: 'openai' | 'gemini';
	provider_name: string;
}

export async function fetchVoiceConfig(): Promise<VoiceConfig> {
	const res = await fetch(`${BASE}/api/voice/config`);
	return asJson<VoiceConfig>(res);
}
