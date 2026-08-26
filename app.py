def gemini(
    prompt,
    *,
    image_bytes=None,
    image_mime="image/jpeg",
    json_mode=False,
    grounded=False,
    thinking_level="medium",
):
    if not GEMINI_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured in Render Environment Variables."
        )

    import requests

    url = (
        "https://generativelanguage.googleapis.com/"
        f"v1beta/models/{GEMINI_MODEL}:generateContent"
    )

    parts = [
        {
            "text": prompt
        }
    ]

    if image_bytes:
        parts.append(
            {
                "inlineData": {
                    "mimeType": image_mime,
                    "data": base64.b64encode(
                        image_bytes
                    ).decode("ascii"),
                }
            }
        )

    generation_config = {}

    if thinking_level:
        generation_config["thinkingConfig"] = {
            "thinkingLevel": thinking_level
        }

    if json_mode:
        generation_config["responseMimeType"] = (
            "application/json"
        )

    body = {
        "contents": [
            {
                "role": "user",
                "parts": parts,
            }
        ],
        "generationConfig": generation_config,
    }

    # IMPORTANT:
    # Gemini REST API uses googleSearch, not google_search.
    if grounded:
        body["tools"] = [
            {
                "googleSearch": {}
            }
        ]

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": GEMINI_KEY,
    }

    last_error = None

    for attempt in range(3):
        try:
            response = requests.post(
                url,
                headers=headers,
                json=body,
                timeout=180,
            )

            if response.ok:
                data = response.json()

                candidates = data.get("candidates") or []

                if not candidates:
                    raise RuntimeError(
                        "Gemini returned no candidates."
                    )

                content = (
                    candidates[0].get("content")
                    or {}
                )

                output_parts = (
                    content.get("parts")
                    or []
                )

                text_parts = [
                    part.get("text", "")
                    for part in output_parts
                    if part.get("text")
                ]

                if not text_parts:
                    raise RuntimeError(
                        "Gemini returned no usable answer."
                    )

                return "\n".join(text_parts), data

            last_error = (
                f"Gemini API error {response.status_code}: "
                f"{response.text[:2000]}"
            )

            if response.status_code not in (
                429,
                500,
                502,
                503,
                504,
            ):
                break

            if attempt < 2:
                time.sleep(2 ** attempt)

        except Exception as exc:
            last_error = str(exc)

            if attempt < 2:
                time.sleep(2 ** attempt)

    raise RuntimeError(
        last_error or "Gemini request failed."
    )
