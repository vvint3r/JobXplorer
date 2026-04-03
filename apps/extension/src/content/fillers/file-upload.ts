// ── File Upload Utility ──────────────────────────────────────────────────────
// Uses the DataTransfer API to programmatically set files on <input type="file">
// elements, since content scripts cannot use file paths like Selenium can.

/**
 * Upload a file (from base64 data) to a file input element.
 * The background worker fetches the PDF as base64 and passes it here.
 */
export function uploadFileFromBase64(
  input: HTMLInputElement,
  base64Data: string,
  filename: string,
  mimeType = "application/pdf",
): boolean {
  try {
    const binaryStr = atob(base64Data);
    const bytes = new Uint8Array(binaryStr.length);
    for (let i = 0; i < binaryStr.length; i++) {
      bytes[i] = binaryStr.charCodeAt(i);
    }

    const file = new File([bytes], filename, { type: mimeType });
    const dt = new DataTransfer();
    dt.items.add(file);

    // Use the native property setter to bypass React/framework wrappers
    const nativeFilesSetter = Object.getOwnPropertyDescriptor(
      HTMLInputElement.prototype,
      "files",
    )?.set;

    if (nativeFilesSetter) {
      nativeFilesSetter.call(input, dt.files);
    } else {
      // Fallback: direct assignment (works in most browsers)
      input.files = dt.files;
    }

    // Dispatch events to notify frameworks
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));

    return true;
  } catch (err) {
    console.error("[file-upload] Error uploading file:", err);
    return false;
  }
}

/**
 * Find a file input element from a list of CSS selectors and upload a file.
 */
export function uploadToFirstMatch(
  selectors: string[],
  base64Data: string,
  filename: string,
): boolean {
  for (const sel of selectors) {
    const input = document.querySelector<HTMLInputElement>(sel);
    if (input && input.type === "file") {
      return uploadFileFromBase64(input, base64Data, filename);
    }
  }
  return false;
}
