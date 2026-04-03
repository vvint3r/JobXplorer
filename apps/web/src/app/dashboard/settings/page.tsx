"use client";

import { useEffect, useRef, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { ApiClient } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

type Tab = "personal" | "application" | "disclosures" | "preferences" | "integrations";

export default function SettingsPage() {
  const [tab, setTab] = useState<Tab>("personal");
  const [profile, setProfile] = useState<any>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const supabase = createClient();

  // --- Personal Info ---
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [location, setLocation] = useState("");
  const [city, setCity] = useState("");
  const [zipCode, setZipCode] = useState("");
  const [linkedin, setLinkedin] = useState("");

  // --- Application Info ---
  const [howDidYouHear, setHowDidYouHear] = useState("LinkedIn");
  const [authorizedToWork, setAuthorizedToWork] = useState(true);
  const [requiresSponsorship, setRequiresSponsorship] = useState(false);
  const [metroArea, setMetroArea] = useState("");

  // --- Voluntary Disclosures ---
  const [gender, setGender] = useState("");
  const [raceEthnicity, setRaceEthnicity] = useState<string[]>([]);
  const [veteranStatus, setVeteranStatus] = useState("");
  const [disability, setDisability] = useState("");

  // --- Search Preferences ---
  const [defaultSalaryMin, setDefaultSalaryMin] = useState("");
  const [defaultSalaryMax, setDefaultSalaryMax] = useState("");
  const [defaultJobType, setDefaultJobType] = useState("full_time");
  const [defaultRemote, setDefaultRemote] = useState("remote");

  // --- Integrations ---
  const [openaiKey, setOpenaiKey] = useState("");
  const [savingKey, setSavingKey] = useState(false);
  const [hasOpenaiKey, setHasOpenaiKey] = useState(false);
  const [cookiesStatus, setCookiesStatus] = useState<{ uploaded: boolean }>({ uploaded: false });
  const [uploadingCookies, setUploadingCookies] = useState(false);
  const cookiesFileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    loadProfile();
  }, []);

  async function getApi() {
    const { data: { session } } = await supabase.auth.getSession();
    if (!session) return null;
    return new ApiClient(session.access_token);
  }

  async function loadProfile() {
    const api = await getApi();
    if (!api) return;

    const [result, cookiesStat] = await Promise.all([
      api.getProfile().catch(() => null),
      api.getLinkedInCookiesStatus().catch(() => ({ uploaded: false })),
    ]);

    if (!result) return;
    const p = result as any;
    setProfile(p);

    // Personal info
    const info = p.personal_info || {};
    setFirstName(info.first_name || "");
    setLastName(info.last_name || "");
    setEmail(info.email || p.email || "");
    setPhone(info.phone || "");
    setLocation(info.location || "");
    setCity(info.city || "");
    setZipCode(info.zip_code || "");
    setLinkedin(info.linkedin_profile || "");

    // Application info
    const app = p.application_info || {};
    setHowDidYouHear(app.how_did_you_hear || "LinkedIn");
    setMetroArea(app.metro_area || "");

    // Work authorization
    const auth = p.work_authorization || {};
    setAuthorizedToWork(auth.authorized_to_work !== false);
    setRequiresSponsorship(auth.requires_sponsorship === true);

    // Voluntary disclosures
    const disc = p.voluntary_disclosures || {};
    setGender(disc.gender_identity || "");
    setRaceEthnicity(disc.race_ethnicity || []);
    setVeteranStatus(disc.veteran_status || "");
    setDisability(disc.disability || "");

    // Search preferences
    const prefs = p.search_preferences || {};
    setDefaultSalaryMin(prefs.salary_min?.toString() || "");
    setDefaultSalaryMax(prefs.salary_max?.toString() || "");
    setDefaultJobType(prefs.job_type || "full_time");
    setDefaultRemote(prefs.remote_filter || "remote");

    // Integrations
    setHasOpenaiKey(!!p.openai_api_key_encrypted);
    setCookiesStatus(cookiesStat as any);
  }

  async function handleSave() {
    setSaving(true);
    setSaved(false);
    const api = await getApi();
    if (!api) return;

    await api.updateProfile({
      full_name: `${firstName} ${lastName}`.trim(),
      personal_info: {
        first_name: firstName,
        last_name: lastName,
        email,
        phone,
        location,
        city,
        zip_code: zipCode,
        linkedin_profile: linkedin,
      },
      application_info: {
        how_did_you_hear: howDidYouHear,
        legally_authorized_to_work: authorizedToWork ? "Yes" : "No",
        require_visa_sponsorship: requiresSponsorship ? "Yes" : "No",
        metro_area: metroArea,
      },
      work_authorization: {
        authorized_to_work: authorizedToWork,
        requires_sponsorship: requiresSponsorship,
      },
      voluntary_disclosures: {
        gender_identity: gender,
        race_ethnicity: raceEthnicity,
        veteran_status: veteranStatus,
        disability,
      },
      search_preferences: {
        salary_min: defaultSalaryMin ? parseInt(defaultSalaryMin) : null,
        salary_max: defaultSalaryMax ? parseInt(defaultSalaryMax) : null,
        job_type: defaultJobType,
        remote_filter: defaultRemote,
      },
    });

    setSaving(false);
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  }

  async function handleSaveOpenAIKey() {
    setSavingKey(true);
    const api = await getApi();
    if (!api) return;
    await api.updateOpenAIKey(openaiKey);
    setOpenaiKey("");
    setHasOpenaiKey(true);
    setSavingKey(false);
  }

  async function handleDeleteOpenAIKey() {
    const api = await getApi();
    if (!api) return;
    await api.deleteOpenAIKey();
    setHasOpenaiKey(false);
  }

  async function handleUploadCookies() {
    const file = cookiesFileRef.current?.files?.[0];
    if (!file) return;
    setUploadingCookies(true);
    const api = await getApi();
    if (!api) return;
    await api.uploadLinkedInCookies(file);
    setCookiesStatus({ uploaded: true });
    if (cookiesFileRef.current) cookiesFileRef.current.value = "";
    setUploadingCookies(false);
  }

  async function handleDeleteCookies() {
    const api = await getApi();
    if (!api) return;
    await api.deleteLinkedInCookies();
    setCookiesStatus({ uploaded: false });
  }

  const tabs: { key: Tab; label: string }[] = [
    { key: "personal", label: "Personal Info" },
    { key: "application", label: "Application" },
    { key: "disclosures", label: "Disclosures" },
    { key: "preferences", label: "Preferences" },
    { key: "integrations", label: "Integrations" },
  ];

  return (
    <div className="space-y-6 max-w-2xl">
      <h1 className="text-3xl font-bold">Settings</h1>

      {/* Tab bar */}
      <div className="flex gap-1 border-b">
        {tabs.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              tab === key
                ? "border-primary text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Personal Info Tab */}
      {tab === "personal" && (
        <Card>
          <CardHeader>
            <CardTitle>Personal Information</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium">First name</label>
                <Input value={firstName} onChange={(e) => setFirstName(e.target.value)} />
              </div>
              <div>
                <label className="text-sm font-medium">Last name</label>
                <Input value={lastName} onChange={(e) => setLastName(e.target.value)} />
              </div>
            </div>
            <div>
              <label className="text-sm font-medium">Email</label>
              <Input value={email} onChange={(e) => setEmail(e.target.value)} type="email" />
            </div>
            <div>
              <label className="text-sm font-medium">Phone</label>
              <Input value={phone} onChange={(e) => setPhone(e.target.value)} type="tel" />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium">Location</label>
                <Input value={location} onChange={(e) => setLocation(e.target.value)} placeholder="City, State" />
              </div>
              <div>
                <label className="text-sm font-medium">ZIP Code</label>
                <Input value={zipCode} onChange={(e) => setZipCode(e.target.value)} />
              </div>
            </div>
            <div>
              <label className="text-sm font-medium">LinkedIn Profile URL</label>
              <Input value={linkedin} onChange={(e) => setLinkedin(e.target.value)} placeholder="https://linkedin.com/in/..." />
            </div>
          </CardContent>
        </Card>
      )}

      {/* Application Info Tab */}
      {tab === "application" && (
        <Card>
          <CardHeader>
            <CardTitle>Application Defaults</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <Toggle label="Authorized to work in the US?" value={authorizedToWork} onChange={setAuthorizedToWork} />
            <Toggle label="Require visa sponsorship?" value={requiresSponsorship} onChange={setRequiresSponsorship} />
            <div>
              <label className="text-sm font-medium">How did you hear about us? (default answer)</label>
              <select
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={howDidYouHear}
                onChange={(e) => setHowDidYouHear(e.target.value)}
              >
                <option>LinkedIn</option>
                <option>Indeed</option>
                <option>Glassdoor</option>
                <option>Referral</option>
                <option>Company Website</option>
                <option>Other</option>
              </select>
            </div>
            <div>
              <label className="text-sm font-medium">Metro area</label>
              <Input value={metroArea} onChange={(e) => setMetroArea(e.target.value)} placeholder="e.g., San Francisco Bay Area" />
            </div>
          </CardContent>
        </Card>
      )}

      {/* Voluntary Disclosures Tab */}
      {tab === "disclosures" && (
        <Card>
          <CardHeader>
            <CardTitle>Voluntary Disclosures</CardTitle>
            <p className="text-sm text-muted-foreground">
              These are optional. They are used to auto-fill voluntary disclosure forms on job applications.
            </p>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="text-sm font-medium">Gender identity</label>
              <select
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={gender}
                onChange={(e) => setGender(e.target.value)}
              >
                <option value="">Prefer not to answer</option>
                <option>Male</option>
                <option>Female</option>
                <option>Non-binary</option>
                <option>Prefer to self-describe</option>
              </select>
            </div>
            <div>
              <label className="text-sm font-medium">Race/ethnicity</label>
              <div className="mt-1 space-y-2">
                {["White", "Black or African American", "Hispanic or Latino", "Asian", "American Indian or Alaska Native", "Native Hawaiian or Other Pacific Islander", "Two or more races", "Prefer not to answer"].map((opt) => (
                  <label key={opt} className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={raceEthnicity.includes(opt)}
                      onChange={(e) => {
                        if (e.target.checked) setRaceEthnicity([...raceEthnicity, opt]);
                        else setRaceEthnicity(raceEthnicity.filter((r) => r !== opt));
                      }}
                      className="rounded border-input"
                    />
                    {opt}
                  </label>
                ))}
              </div>
            </div>
            <div>
              <label className="text-sm font-medium">Veteran status</label>
              <select
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={veteranStatus}
                onChange={(e) => setVeteranStatus(e.target.value)}
              >
                <option value="">Prefer not to answer</option>
                <option>I am not a protected veteran</option>
                <option>I identify as one or more of the classifications of a protected veteran</option>
              </select>
            </div>
            <div>
              <label className="text-sm font-medium">Disability status</label>
              <select
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={disability}
                onChange={(e) => setDisability(e.target.value)}
              >
                <option value="">Prefer not to answer</option>
                <option>Yes, I have a disability (or previously had a disability)</option>
                <option>No, I don&apos;t have a disability</option>
              </select>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Search Preferences Tab */}
      {tab === "preferences" && (
        <Card>
          <CardHeader>
            <CardTitle>Default Search Preferences</CardTitle>
            <p className="text-sm text-muted-foreground">
              These defaults are used when creating new search configs.
            </p>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium">Min salary ($)</label>
                <Input
                  type="number"
                  value={defaultSalaryMin}
                  onChange={(e) => setDefaultSalaryMin(e.target.value)}
                  placeholder="e.g., 120000"
                />
              </div>
              <div>
                <label className="text-sm font-medium">Max salary ($)</label>
                <Input
                  type="number"
                  value={defaultSalaryMax}
                  onChange={(e) => setDefaultSalaryMax(e.target.value)}
                  placeholder="e.g., 200000"
                />
              </div>
            </div>
            <div>
              <label className="text-sm font-medium">Job type</label>
              <select
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={defaultJobType}
                onChange={(e) => setDefaultJobType(e.target.value)}
              >
                <option value="full_time">Full-time</option>
                <option value="contract">Contract</option>
                <option value="part_time">Part-time</option>
                <option value="internship">Internship</option>
              </select>
            </div>
            <div>
              <label className="text-sm font-medium">Remote preference</label>
              <select
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={defaultRemote}
                onChange={(e) => setDefaultRemote(e.target.value)}
              >
                <option value="remote">Remote</option>
                <option value="hybrid">Hybrid</option>
                <option value="onsite">On-site</option>
                <option value="">No preference</option>
              </select>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Integrations Tab */}
      {tab === "integrations" && (
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>OpenAI API Key</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-muted-foreground">
                Required for AI-powered resume optimization and input index generation. Your key is encrypted at rest.
              </p>
              {hasOpenaiKey ? (
                <div className="flex items-center justify-between rounded-md border p-3">
                  <div className="flex items-center gap-2">
                    <Badge variant="success">Configured</Badge>
                    <span className="text-sm text-muted-foreground">sk-...****</span>
                  </div>
                  <Button variant="destructive" size="sm" onClick={handleDeleteOpenAIKey}>
                    Remove
                  </Button>
                </div>
              ) : (
                <div className="flex gap-4">
                  <Input
                    value={openaiKey}
                    onChange={(e) => setOpenaiKey(e.target.value)}
                    type="password"
                    placeholder="sk-..."
                    className="flex-1"
                  />
                  <Button onClick={handleSaveOpenAIKey} disabled={savingKey || !openaiKey}>
                    {savingKey ? "Saving..." : "Save Key"}
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>LinkedIn Cookies</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-muted-foreground">
                Upload your LinkedIn session cookies for job scraping. Generate them by running the manual login script locally.
              </p>
              {cookiesStatus.uploaded ? (
                <div className="flex items-center justify-between rounded-md border p-3">
                  <div className="flex items-center gap-2">
                    <Badge variant="success">Uploaded</Badge>
                    <span className="text-sm text-muted-foreground">linkedin_cookies.txt</span>
                  </div>
                  <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={() => setCookiesStatus({ uploaded: false })}>
                      Replace
                    </Button>
                    <Button variant="destructive" size="sm" onClick={handleDeleteCookies}>
                      Delete
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="flex gap-4 items-end">
                  <div className="flex-1">
                    <input
                      ref={cookiesFileRef}
                      type="file"
                      accept=".txt"
                      className="block w-full text-sm text-muted-foreground file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-medium file:bg-secondary file:text-secondary-foreground hover:file:opacity-80"
                    />
                  </div>
                  <Button onClick={handleUploadCookies} disabled={uploadingCookies}>
                    {uploadingCookies ? "Uploading..." : "Upload"}
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* Save button (visible on profile tabs, not integrations) */}
      {tab !== "integrations" && (
        <div className="flex items-center gap-3">
          <Button onClick={handleSave} disabled={saving}>
            {saving ? "Saving..." : "Save All Settings"}
          </Button>
          {saved && <span className="text-sm text-green-600">Settings saved!</span>}
        </div>
      )}
    </div>
  );
}

function Toggle({ label, value, onChange }: { label: string; value: boolean; onChange: (v: boolean) => void }) {
  return (
    <div className="flex items-center justify-between rounded-md border p-3">
      <label className="text-sm font-medium">{label}</label>
      <button
        type="button"
        onClick={() => onChange(!value)}
        className={`relative inline-flex h-6 w-11 items-center rounded-full transition ${value ? "bg-primary" : "bg-muted"}`}
      >
        <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition ${value ? "translate-x-6" : "translate-x-1"}`} />
      </button>
    </div>
  );
}
