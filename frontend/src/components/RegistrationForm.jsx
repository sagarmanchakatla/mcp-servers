import React, { useState } from "react";

export default function RegisterForm() {
  const [formData, setFormData] = useState({
    token: "abc123", // Replace or set dynamically
    owner_name: "",
    owner_contact: "",
    business_name: "",
    business_type: "Kirana Store",
    description: "",
    address: "",
    city: "",
    postal_code: "",
    delivery_available: false,
    delivery_radius: "",
    payment_modes: [],
    item_name: "",
    item_sku: "",
    item_category: "",
    item_price: "",
    item_qty: "",
    item_unit: "",
  });

  const paymentOptions = ["Cash", "Card", "UPI", "NetBanking", "Wallet"];

  const handleChange = (e) => {
    const { name, value, type, checked, options } = e.target;

    if (type === "checkbox") {
      setFormData((prev) => ({
        ...prev,
        [name]: checked,
      }));
    } else if (type === "select-multiple") {
      const selectedOptions = Array.from(options)
        .filter((opt) => opt.selected)
        .map((opt) => opt.value);
      setFormData((prev) => ({
        ...prev,
        [name]: selectedOptions,
      }));
    } else {
      setFormData((prev) => ({
        ...prev,
        [name]: value,
      }));
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    // Prepare form data for submission as URLSearchParams
    const payload = new URLSearchParams();

    // Append each field, convert arrays to comma-separated strings
    for (const key in formData) {
      if (Array.isArray(formData[key])) {
        payload.append(key, formData[key].join(","));
      } else {
        payload.append(key, formData[key]);
      }
    }

    try {
      const response = await fetch("http://0.0.0.0:8087/register/submit", {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
        body: payload.toString(),
      });

      if (response.ok) {
        alert("Registration successful!");
        // Optionally reset form or redirect
      } else {
        const text = await response.text();
        alert("Failed to register: " + text);
      }
    } catch (err) {
      alert("Error submitting form: " + err.message);
    }
  };

  return (
    <form onSubmit={handleSubmit} style={{ maxWidth: 600, margin: "auto" }}>
      <h3>Owner Information</h3>
      <label>
        Owner Name:
        <br />
        <input
          type="text"
          name="owner_name"
          value={formData.owner_name}
          onChange={handleChange}
          required
        />
      </label>
      <br />

      <label>
        Owner Contact:
        <br />
        <input
          type="tel"
          name="owner_contact"
          value={formData.owner_contact}
          onChange={handleChange}
          required
        />
      </label>
      <br />

      <h3>Business Information</h3>
      <label>
        Business Name:
        <br />
        <input
          type="text"
          name="business_name"
          value={formData.business_name}
          onChange={handleChange}
          required
        />
      </label>
      <br />

      <label>
        Business Type:
        <br />
        <select
          name="business_type"
          value={formData.business_type}
          onChange={handleChange}
          required
          disabled
        >
          <option value="Kirana Store">Kirana Store</option>
        </select>
      </label>
      <br />

      <label>
        Description:
        <br />
        <textarea
          name="description"
          value={formData.description}
          onChange={handleChange}
          rows={3}
        />
      </label>
      <br />

      <label>
        Address:
        <br />
        <input
          type="text"
          name="address"
          value={formData.address}
          onChange={handleChange}
          required
        />
      </label>
      <br />

      <label>
        City:
        <br />
        <input
          type="text"
          name="city"
          value={formData.city}
          onChange={handleChange}
          required
        />
      </label>
      <br />

      <label>
        Postal Code:
        <br />
        <input
          type="text"
          name="postal_code"
          value={formData.postal_code}
          onChange={handleChange}
          required
        />
      </label>
      <br />

      <label>
        Delivery Available:{" "}
        <input
          type="checkbox"
          name="delivery_available"
          checked={formData.delivery_available}
          onChange={handleChange}
        />
      </label>
      <br />

      <label>
        Delivery Radius (km):
        <br />
        <input
          type="number"
          name="delivery_radius"
          value={formData.delivery_radius}
          onChange={handleChange}
          min="0"
          step="0.1"
          disabled={!formData.delivery_available}
        />
      </label>
      <br />

      <label>
        Payment Modes:
        <br />
        <select
          name="payment_modes"
          multiple
          value={formData.payment_modes}
          onChange={handleChange}
          size={paymentOptions.length}
        >
          {paymentOptions.map((opt) => (
            <option key={opt} value={opt}>
              {opt}
            </option>
          ))}
        </select>
      </label>
      <br />

      <h3>Initial Inventory Item (Optional)</h3>

      <label>
        Item Name:
        <br />
        <input
          type="text"
          name="item_name"
          value={formData.item_name}
          onChange={handleChange}
        />
      </label>
      <br />

      <label>
        Item SKU:
        <br />
        <input
          type="text"
          name="item_sku"
          value={formData.item_sku}
          onChange={handleChange}
        />
      </label>
      <br />

      <label>
        Item Category:
        <br />
        <input
          type="text"
          name="item_category"
          value={formData.item_category}
          onChange={handleChange}
        />
      </label>
      <br />

      <label>
        Item Price:
        <br />
        <input
          type="number"
          name="item_price"
          value={formData.item_price}
          onChange={handleChange}
          min="0"
          step="0.01"
        />
      </label>
      <br />

      <label>
        Item Quantity:
        <br />
        <input
          type="number"
          name="item_qty"
          value={formData.item_qty}
          onChange={handleChange}
          min="0"
        />
      </label>
      <br />

      <label>
        Item Unit:
        <br />
        <input
          type="text"
          name="item_unit"
          value={formData.item_unit}
          onChange={handleChange}
          placeholder="e.g. pcs, kg"
        />
      </label>
      <br />

      <button type="submit">Register Business</button>
    </form>
  );
}
