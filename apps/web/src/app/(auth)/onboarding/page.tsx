"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { ApiClient } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function OnboardingPage() {
  const [step, setStep] = useState(1);
  const [saving, setSaving] = useState(false);
  const router = useRouter();
  const supabase = createClient();

  // Step 1: Personal info
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [phone, setPhone] = useState("");
  const [location, setLocation] = useState("");
  const [linkedin, setLinkedin] = useState("");

  // Step 2: Work authorization
  const [authorizedToWork, setAuthorizedToWork] = useState(true);
  const [requiresSponsorship, setRequiresSponsorship] = useState(false);
  const [howDidYouHear, setHowDidYouHear] = useState("LinkedIn");

  async function handleComplete() {
    setSaving(true);
    const { data: { session } } = await supabase.auth.getSession();
    if (!session) return;

    const api = new ApiClient(session.access_token);
    await api.updateProfile({
      full_name: `${firstName} ${lastName}`.trim(),
      personal_info: {
        first_name: firstName,
        last_name: lastName,
        email: session.user.email,
        phone,
        location,
        linkedin_profile: linkedin,
      },
      application_info: {
        how_did_you_hear: howDidYouHear,
        legally_authorized_to_work: authorizedToWork ? "Yes" : "No",
        require_visa_sponsorship: requiresSponsorship ? "Yes" : "No",
      },
      work_authorization: {
        authorized_to_work: authorizedToWork,
        requires_sponsorship: requiresSponsorship,
      },
    });

    setSaving(false);
    router.push("/dashboard");
  }

  return (
    <main className="flex min-h-screen items-center justify-center p-4">
      <Card className="w-full max-w-lg">
        <CardHeader>
          <CardTitle>Welcome to JobXplore</CardTitle>
          <CardDescription>
            {step === 1
              ? "Let's set up your profile (Step 1 of 2)"
              : "Almost done! (Step 2 of 2)"}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {step === 1 ? (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium">First name *</label>
                  <Input value={firstName} onChange={(e) => setFirstName(e.target.value)} />
                </div>
                <div>
                  <label className="text-sm font-medium">Last name *</label>
                  <Input value={lastName} onChange={(e) => setLastName(e.target.value)} />
                </div>
              </div>
              <div>
                <label className="text-sm font-medium">Phone</label>
                <Input value={phone} onChange={(e) => setPhone(e.target.value)} type="tel" placeholder="+1 (555) 123-4567" />
              </div>
              <div>
                <label className="text-sm font-medium">Location</label>
                <Input value={location} onChange={(e) => setLocation(e.target.value)} placeholder="City, State" />
              </div>
              <div>
                <label className="text-sm font-medium">LinkedIn URL</label>
                <Input value={linkedin} onChange={(e) => setLinkedin(e.target.value)} placeholder="https://linkedin.com/in/..." />
              </div>
              <Button
                className="w-full"
                onClick={() => setStep(2)}
                disabled={!firstName || !lastName}
              >
                Next
              </Button>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="flex items-center justify-between rounded-md border p-3">
                <label className="text-sm font-medium">Authorized to work in the US?</label>
                <button
                  type="button"
                  onClick={() => setAuthorizedToWork(!authorizedToWork)}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition ${authorizedToWork ? "bg-primary" : "bg-muted"}`}
                >
                  <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition ${authorizedToWork ? "translate-x-6" : "translate-x-1"}`} />
                </button>
              </div>
              <div className="flex items-center justify-between rounded-md border p-3">
                <label className="text-sm font-medium">Require visa sponsorship?</label>
                <button
                  type="button"
                  onClick={() => setRequiresSponsorship(!requiresSponsorship)}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition ${requiresSponsorship ? "bg-primary" : "bg-muted"}`}
                >
                  <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition ${requiresSponsorship ? "translate-x-6" : "translate-x-1"}`} />
                </button>
              </div>
              <div>
                <label className="text-sm font-medium">How did you hear about us?</label>
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
              <div className="flex gap-3 pt-2">
                <Button variant="outline" onClick={() => setStep(1)} className="flex-1">
                  Back
                </Button>
                <Button onClick={handleComplete} disabled={saving} className="flex-1">
                  {saving ? "Saving..." : "Complete Setup"}
                </Button>
              </div>
              <button
                onClick={() => router.push("/dashboard")}
                className="w-full text-sm text-muted-foreground hover:text-foreground"
              >
                Skip for now
              </button>
            </div>
          )}
        </CardContent>
      </Card>
    </main>
  );
}
