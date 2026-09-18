// Curated option lists for the Discover form. Business types mirror the
// OpenStreetMap provider's exact tag mapping (app/providers/lead_sources/
// osm_provider.py _INDUSTRY_TAGS on the backend) — picking one of these
// guarantees a real category match instead of falling through to a
// narrow literal name search. Country/state are full names because
// that's what the Nominatim geocoder actually resolves reliably.

export const BUSINESS_TYPES: { value: string; label: string }[] = [
  { value: "", label: "Other (enter a keyword below)" },
  { value: "dentist", label: "Dentist / dental clinic" },
  { value: "restaurant", label: "Restaurant" },
  { value: "cafe", label: "Cafe / coffee shop" },
  { value: "hotel", label: "Hotel" },
  { value: "gym", label: "Gym / fitness center" },
  { value: "roofing", label: "Roofing contractor" },
  { value: "plumber", label: "Plumber" },
  { value: "electrician", label: "Electrician" },
  { value: "hardware", label: "Hardware store" },
  { value: "bakery", label: "Bakery" },
  { value: "bank", label: "Bank" },
  { value: "pharmacy", label: "Pharmacy" },
  { value: "hairdresser", label: "Hair salon" },
  { value: "car_repair", label: "Auto repair shop" },
];

export const COUNTRIES: string[] = [
  "United States",
  "Canada",
  "United Kingdom",
  "Ireland",
  "Australia",
  "New Zealand",
  "Germany",
  "France",
  "Spain",
  "Italy",
  "Portugal",
  "Netherlands",
  "Belgium",
  "Switzerland",
  "Austria",
  "Sweden",
  "Norway",
  "Denmark",
  "Finland",
  "Poland",
  "Mexico",
  "Brazil",
  "Argentina",
  "India",
  "Singapore",
  "Japan",
  "South Korea",
  "United Arab Emirates",
  "South Africa",
];

export const US_STATES: string[] = [
  "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado", "Connecticut",
  "Delaware", "District of Columbia", "Florida", "Georgia", "Hawaii", "Idaho", "Illinois",
  "Indiana", "Iowa", "Kansas", "Kentucky", "Louisiana", "Maine", "Maryland", "Massachusetts",
  "Michigan", "Minnesota", "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada",
  "New Hampshire", "New Jersey", "New Mexico", "New York", "North Carolina", "North Dakota",
  "Ohio", "Oklahoma", "Oregon", "Pennsylvania", "Rhode Island", "South Carolina",
  "South Dakota", "Tennessee", "Texas", "Utah", "Vermont", "Virginia", "Washington",
  "West Virginia", "Wisconsin", "Wyoming",
];

export const RESULT_LIMITS = [10, 25, 50, 100];
