"""
Size-guide charts, one per size system.

Sizing depends on the footwear type, so the product page shows the chart
that matches the product's ``size_system``:

* ``adult`` -- UK/India 3–12 with EU size and foot length in cm
* ``kids``  -- kids UK 1–13 with EU size, an age hint and foot length
* ``label`` -- S / M / L (slippers, flip-flops, floaters) with a cm range

Pure data, no Django imports -- kept separate from models so it stays easy
to read and to extend.
"""

SIZE_GUIDES = {
    # ---------------------------------------------------------- adults ---
    "adult": {
        "title": "Adult size guide (UK / India)",
        "note": (
            "Place your heel against a wall and measure to the tip of your "
            "longest toe. Match the length below — if you are between sizes, "
            "size up."
        ),
        "columns": ["UK / India", "EU", "Foot length (cm)"],
        "rows": [
            ("3", "35.5", "22.5"),
            ("4", "36.5", "23.3"),
            ("5", "38", "24.1"),
            ("6", "39", "24.9"),
            ("7", "40.5", "25.7"),
            ("8", "42", "26.5"),
            ("9", "43", "27.3"),
            ("10", "44", "28.1"),
            ("11", "45", "29.0"),
            ("12", "46", "29.8"),
        ],
    },
    # ------------------------------------------------------------ kids ---
    "kids": {
        "title": "Kids size guide (UK)",
        "note": (
            "Kids' feet grow fast — measure both feet and use the longer "
            "measurement. Ages are a guide only; the foot length in cm is "
            "what matters."
        ),
        "columns": ["Kids UK", "EU", "Approx. age", "Foot length (cm)"],
        "rows": [
            ("1", "17", "0–6 months", "10.5"),
            ("2", "18", "6–12 months", "11.5"),
            ("3", "19", "12–18 months", "12.5"),
            ("4", "20", "1½–2½ years", "13.5"),
            ("5", "21", "2½–3½ years", "14.5"),
            ("6", "22", "3½–4½ years", "15.5"),
            ("7", "24", "4½–5½ years", "16.5"),
            ("8", "25", "5½–6½ years", "17.5"),
            ("9", "26", "6½–7½ years", "18.5"),
            ("10", "27", "7½–8½ years", "19.5"),
            ("11", "28", "8½–9½ years", "20.5"),
            ("12", "29", "9½–10½ years", "21.5"),
            ("13", "30", "10½–11½ years", "22.5"),
        ],
    },
    # ------------------------------------------------- S / M / L labels ---
    "label": {
        "title": "Size guide (S / M / L)",
        "note": (
            "Slippers, flip-flops and floaters are sized by foot length. "
            "If you are between two sizes, pick the larger one."
        ),
        "columns": ["Size", "Foot length (cm)"],
        "rows": [
            ("S", "up to 23.0"),
            ("M", "23.1 – 25.5"),
            ("L", "25.6 – 28.0"),
        ],
    },
}
