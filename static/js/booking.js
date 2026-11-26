// Booking Wizard, Saved Vehicles/Addresses & Free OpenStreetMap Coordinate Picker Logic
document.addEventListener('DOMContentLoaded', () => {
  const vehicleBtns = document.querySelectorAll('.vehicle-btn');
  const vehicleInput = document.getElementById('vehicle_type_input');
  const packageCards = document.querySelectorAll('.package-card');
  const dateInput = document.getElementById('booking_date');
  const slotContainer = document.getElementById('slotContainer');
  const slotLoading = document.getElementById('slotLoading');
  const selectedTimeInput = document.getElementById('booking_time');
  const selectedPackageInput = document.getElementById('package_id');
  const summaryPackageName = document.getElementById('summaryPackageName');
  const summaryPrice = document.getElementById('summaryPrice');
  const summaryTime = document.getElementById('summaryTime');
  const submitBtn = document.getElementById('submitBookingBtn');

  // Vehicle Elements
  const userVehicleSelect = document.getElementById('user_vehicle_select');
  const btnToggleNewVehicle = document.getElementById('btnToggleNewVehicle');
  const btnCancelNewVehicle = document.getElementById('btnCancelNewVehicle');
  const newVehicleInlineBox = document.getElementById('newVehicleInlineBox');
  const inlineVehicleType = document.getElementById('inline_vehicle_type');
  const inlineVehicleModel = document.getElementById('inline_vehicle_model');
  const inlineLicensePlate = document.getElementById('inline_license_plate');
  const btnSaveInlineVehicle = document.getElementById('btnSaveInlineVehicle');
  const vehicleModelInput = document.getElementById('vehicle_model');
  const licensePlateInput = document.getElementById('license_plate');
  const activeVehicleDisplay = document.getElementById('activeVehicleDisplay');
  const activeVehicleIcon = document.getElementById('activeVehicleIcon');
  const activeVehicleText = document.getElementById('activeVehicleText');

  // Address & Map Elements
  const userAddressSelect = document.getElementById('user_address_select');
  const btnToggleNewAddress = document.getElementById('btnToggleNewAddress');
  const btnCancelNewAddress = document.getElementById('btnCancelNewAddress');
  const newAddressInlineBox = document.getElementById('newAddressInlineBox');
  const inlineAddressLabel = document.getElementById('inline_address_label');
  const inlineAddressText = document.getElementById('inline_address_text');
  const inlineAddressNotes = document.getElementById('inline_address_notes');
  const btnSaveInlineAddress = document.getElementById('btnSaveInlineAddress');
  const btnGetCurrentLocation = document.getElementById('btnGetCurrentLocation');
  const customerAddressInput = document.getElementById('customer_address');
  const customerNotesInput = document.getElementById('customer_notes');
  const latitudeInput = document.getElementById('latitude');
  const longitudeInput = document.getElementById('longitude');
  const activeAddressDisplay = document.getElementById('activeAddressDisplay');
  const activeAddressText = document.getElementById('activeAddressText');
  const activeAddressCoordText = document.getElementById('activeAddressCoordText');
  const coordDisplay = document.getElementById('coordDisplay');

  // Format currency helper (IDR)
  function formatRupiah(num) {
    return 'Rp ' + Number(num).toLocaleString('id-ID');
  }

  // ==========================================
  // 1. VEHICLE TYPE BUTTONS & SYNCING
  // ==========================================
  vehicleBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      setVehicleCategory(btn.dataset.category);
    });
  });

  function setVehicleCategory(category) {
    vehicleBtns.forEach(b => {
      if (b.dataset.category === category) {
        b.classList.add('active', 'border-sky-600', 'bg-sky-50');
      } else {
        b.classList.remove('active', 'border-sky-600', 'bg-sky-50');
      }
    });

    if (vehicleInput) vehicleInput.value = category;
    if (inlineVehicleType) inlineVehicleType.value = category;
    filterPackages(category);
  }

  // ==========================================
  // 2. SAVED VEHICLES DROPDOWN & INLINE ADD
  // ==========================================
  if (userVehicleSelect) {
    userVehicleSelect.addEventListener('change', () => {
      const selectedOption = userVehicleSelect.options[userVehicleSelect.selectedIndex];
      const val = userVehicleSelect.value;

      if (val === 'new') {
        if (newVehicleInlineBox) newVehicleInlineBox.classList.remove('hidden');
        if (inlineVehicleModel) inlineVehicleModel.focus();
        clearActiveVehicle();
      } else if (val && selectedOption) {
        const vType = selectedOption.dataset.type;
        const vModel = selectedOption.dataset.model;
        const vPlate = selectedOption.dataset.plate;

        applyVehicleData(vType, vModel, vPlate);
        if (newVehicleInlineBox) newVehicleInlineBox.classList.add('hidden');
      } else {
        clearActiveVehicle();
      }
      validateForm();
    });

    // Auto-select first vehicle if available
    if (userVehicleSelect.options.length > 2 && userVehicleSelect.selectedIndex <= 0) {
      userVehicleSelect.selectedIndex = 1;
      userVehicleSelect.dispatchEvent(new Event('change'));
    }
  }

  function applyVehicleData(type, model, plate) {
    if (vehicleModelInput) vehicleModelInput.value = model;
    if (licensePlateInput) licensePlateInput.value = plate;

    if (activeVehicleDisplay) {
      activeVehicleDisplay.classList.remove('hidden');
      activeVehicleDisplay.classList.add('flex');
    }
    if (activeVehicleIcon) activeVehicleIcon.textContent = (type === 'mobil') ? '🚗' : '🛵';
    if (activeVehicleText) activeVehicleText.textContent = `${model} (${plate})`;

    setVehicleCategory(type);
  }

  function clearActiveVehicle() {
    if (vehicleModelInput) vehicleModelInput.value = '';
    if (licensePlateInput) licensePlateInput.value = '';
    if (activeVehicleDisplay) {
      activeVehicleDisplay.classList.add('hidden');
      activeVehicleDisplay.classList.remove('flex');
    }
  }

  if (btnToggleNewVehicle) {
    btnToggleNewVehicle.addEventListener('click', () => {
      if (newVehicleInlineBox) {
        newVehicleInlineBox.classList.toggle('hidden');
        if (!newVehicleInlineBox.classList.contains('hidden') && inlineVehicleModel) {
          inlineVehicleModel.focus();
        }
      }
    });
  }

  if (btnCancelNewVehicle) {
    btnCancelNewVehicle.addEventListener('click', () => {
      if (newVehicleInlineBox) newVehicleInlineBox.classList.add('hidden');
    });
  }

  if (btnSaveInlineVehicle) {
    btnSaveInlineVehicle.addEventListener('click', () => {
      const vType = inlineVehicleType ? inlineVehicleType.value : 'mobil';
      const vModel = inlineVehicleModel ? inlineVehicleModel.value.trim() : '';
      const vPlate = inlineLicensePlate ? inlineLicensePlate.value.trim().toUpperCase() : '';

      if (!vModel || !vPlate) {
        alert('Harap isi model kendaraan dan nomor plat polisi terlebih dahulu.');
        return;
      }

      btnSaveInlineVehicle.setAttribute('disabled', 'true');
      btnSaveInlineVehicle.textContent = 'Menyimpan...';

      fetch('/api/vehicles/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          vehicle_type: vType,
          vehicle_model: vModel,
          license_plate: vPlate
        })
      })
      .then(res => res.json())
      .then(data => {
        btnSaveInlineVehicle.removeAttribute('disabled');
        btnSaveInlineVehicle.textContent = 'Simpan & Gunakan Kendaraan';

        if (data.success && data.vehicle) {
          const veh = data.vehicle;
          if (userVehicleSelect) {
            const opt = document.createElement('option');
            opt.value = veh.id;
            opt.dataset.type = veh.vehicle_type;
            opt.dataset.model = veh.vehicle_model;
            opt.dataset.plate = veh.license_plate;
            opt.textContent = `${(veh.vehicle_type === 'mobil') ? '🚗 Mobil' : '🛵 Motor'}: ${veh.vehicle_model} (${veh.license_plate})`;

            userVehicleSelect.insertBefore(opt, userVehicleSelect.options[userVehicleSelect.options.length - 1]);
            userVehicleSelect.value = veh.id;
          }

          applyVehicleData(veh.vehicle_type, veh.vehicle_model, veh.license_plate);
          if (newVehicleInlineBox) newVehicleInlineBox.classList.add('hidden');

          if (inlineVehicleModel) inlineVehicleModel.value = '';
          if (inlineLicensePlate) inlineLicensePlate.value = '';

          validateForm();
          if (typeof showToast === 'function') {
            showToast('Kendaraan berhasil disimpan dan dipilih!', 'success');
          }
        } else {
          alert(data.message || 'Gagal menyimpan kendaraan.');
        }
      })
      .catch(err => {
        console.error('Error saving vehicle:', err);
        btnSaveInlineVehicle.removeAttribute('disabled');
        btnSaveInlineVehicle.textContent = 'Simpan & Gunakan Kendaraan';
        alert('Terjadi kesalahan koneksi saat menyimpan kendaraan.');
      });
    });
  }

  // ==========================================
  // 3. SAVED ADDRESSES & FREE MAP COORDINATE PICKER
  // ==========================================
  let leafletMap = null;
  let leafletMarker = null;
  let currentLat = -6.2088; // Default center (Jakarta)
  let currentLng = 106.8456;

  function initLeafletMap() {
    const mapContainer = document.getElementById('mapPicker');
    if (!mapContainer || typeof L === 'undefined') return;
    if (leafletMap) {
      leafletMap.invalidateSize();
      return;
    }

    try {
      leafletMap = L.map('mapPicker').setView([currentLat, currentLng], 14);
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors',
        maxZoom: 19
      }).addTo(leafletMap);

      leafletMarker = L.marker([currentLat, currentLng], { draggable: true }).addTo(leafletMap);

      leafletMarker.on('dragend', () => {
        const pos = leafletMarker.getLatLng();
        updateSelectedCoordinates(pos.lat, pos.lng);
      });

      leafletMap.on('click', (e) => {
        leafletMarker.setLatLng(e.latlng);
        updateSelectedCoordinates(e.latlng.lat, e.latlng.lng);
      });

      updateSelectedCoordinates(currentLat, currentLng);
    } catch (err) {
      console.warn('Leaflet map initialization skipped or offline:', err);
    }
  }

  function updateSelectedCoordinates(lat, lng) {
    currentLat = Number(lat.toFixed(6));
    currentLng = Number(lng.toFixed(6));
    if (coordDisplay) coordDisplay.textContent = `${currentLat}, ${currentLng}`;
    if (latitudeInput) latitudeInput.value = currentLat;
    if (longitudeInput) longitudeInput.value = currentLng;
  }

  // Try GPS Geolocation for precise location
  if (btnGetCurrentLocation) {
    btnGetCurrentLocation.addEventListener('click', () => {
      if ('geolocation' in navigator) {
        btnGetCurrentLocation.innerHTML = '<span>⏳ Mencari sinyal GPS...</span>';
        navigator.geolocation.getCurrentPosition(
          (pos) => {
            btnGetCurrentLocation.innerHTML = '<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"/></svg><span>📍 Lokasi Saya (GPS)</span>';
            const lat = pos.coords.latitude;
            const lng = pos.coords.longitude;
            if (leafletMap && leafletMarker) {
              leafletMap.setView([lat, lng], 16);
              leafletMarker.setLatLng([lat, lng]);
            }
            updateSelectedCoordinates(lat, lng);
            if (typeof showToast === 'function') {
              showToast('Lokasi GPS Anda berhasil ditemukan!', 'success');
            }
          },
          (err) => {
            btnGetCurrentLocation.innerHTML = '<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"/></svg><span>📍 Lokasi Saya (GPS)</span>';
            alert('Tidak dapat mendeteksi GPS secara otomatis. Silakan klik langsung pada peta untuk menentukan titik.');
          },
          { enableHighAccuracy: true, timeout: 8000 }
        );
      } else {
        alert('Browser Anda tidak mendukung deteksi lokasi otomatis.');
      }
    });
  }

  // Address dropdown change handler
  if (userAddressSelect) {
    userAddressSelect.addEventListener('change', () => {
      const selectedOption = userAddressSelect.options[userAddressSelect.selectedIndex];
      const val = userAddressSelect.value;

      if (val === 'new') {
        if (newAddressInlineBox) {
          newAddressInlineBox.classList.remove('hidden');
          setTimeout(() => { initLeafletMap(); }, 200);
        }
        if (inlineAddressText) inlineAddressText.focus();
        clearActiveAddress();
      } else if (val && selectedOption) {
        const addr = selectedOption.dataset.address;
        const notes = selectedOption.dataset.notes || '';
        const lat = selectedOption.dataset.lat || '';
        const lng = selectedOption.dataset.lng || '';

        applyAddressData(addr, notes, lat, lng);
        if (newAddressInlineBox) newAddressInlineBox.classList.add('hidden');
      } else {
        clearActiveAddress();
      }
      validateForm();
    });

    // Auto-select first address if available
    if (userAddressSelect.options.length > 2 && userAddressSelect.selectedIndex <= 0) {
      userAddressSelect.selectedIndex = 1;
      userAddressSelect.dispatchEvent(new Event('change'));
    }
  }

  function applyAddressData(address, notes, lat, lng) {
    if (customerAddressInput) customerAddressInput.value = address;
    if (customerNotesInput) customerNotesInput.value = notes;
    if (latitudeInput) latitudeInput.value = lat;
    if (longitudeInput) longitudeInput.value = lng;

    if (activeAddressDisplay) {
      activeAddressDisplay.classList.remove('hidden');
      activeAddressDisplay.classList.add('flex');
    }
    if (activeAddressText) activeAddressText.textContent = address;
    if (activeAddressCoordText) {
      if (lat && lng) {
        activeAddressCoordText.textContent = `Titik Koordinat: ${lat}, ${lng} (Navigasi Maps Siap)`;
      } else {
        activeAddressCoordText.textContent = `Titik koordinat belum ditandai`;
      }
    }
  }

  function clearActiveAddress() {
    if (customerAddressInput) customerAddressInput.value = '';
    if (customerNotesInput) customerNotesInput.value = '';
    if (latitudeInput) latitudeInput.value = '';
    if (longitudeInput) longitudeInput.value = '';
    if (activeAddressDisplay) {
      activeAddressDisplay.classList.add('hidden');
      activeAddressDisplay.classList.remove('flex');
    }
  }

  if (btnToggleNewAddress) {
    btnToggleNewAddress.addEventListener('click', () => {
      if (newAddressInlineBox) {
        newAddressInlineBox.classList.toggle('hidden');
        if (!newAddressInlineBox.classList.contains('hidden')) {
          setTimeout(() => { initLeafletMap(); }, 200);
          if (inlineAddressText) inlineAddressText.focus();
        }
      }
    });
  }

  if (btnCancelNewAddress) {
    btnCancelNewAddress.addEventListener('click', () => {
      if (newAddressInlineBox) newAddressInlineBox.classList.add('hidden');
    });
  }

  if (btnSaveInlineAddress) {
    btnSaveInlineAddress.addEventListener('click', () => {
      const label = inlineAddressLabel ? inlineAddressLabel.value.trim() : 'Rumah';
      const address = inlineAddressText ? inlineAddressText.value.trim() : '';
      const notes = inlineAddressNotes ? inlineAddressNotes.value.trim() : '';

      if (!address) {
        alert('Harap isi alamat lengkap lokasi cuci.');
        return;
      }

      btnSaveInlineAddress.setAttribute('disabled', 'true');
      btnSaveInlineAddress.textContent = 'Menyimpan...';

      fetch('/api/addresses/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          label: label,
          address: address,
          notes: notes,
          latitude: currentLat,
          longitude: currentLng
        })
      })
      .then(res => res.json())
      .then(data => {
        btnSaveInlineAddress.removeAttribute('disabled');
        btnSaveInlineAddress.textContent = 'Simpan & Gunakan Alamat Ini';

        if (data.success && data.address) {
          const addr = data.address;
          if (userAddressSelect) {
            const opt = document.createElement('option');
            opt.value = addr.id;
            opt.dataset.address = addr.address;
            opt.dataset.notes = addr.notes || '';
            opt.dataset.lat = addr.latitude || '';
            opt.dataset.lng = addr.longitude || '';
            opt.textContent = `📍 ${addr.label}: ${addr.address.substring(0, 45)}${addr.address.length > 45 ? '...' : ''}`;

            userAddressSelect.insertBefore(opt, userAddressSelect.options[userAddressSelect.options.length - 1]);
            userAddressSelect.value = addr.id;
          }

          applyAddressData(addr.address, addr.notes, addr.latitude, addr.longitude);
          if (newAddressInlineBox) newAddressInlineBox.classList.add('hidden');

          validateForm();
          if (typeof showToast === 'function') {
            showToast('Alamat dan titik koordinat peta berhasil disimpan!', 'success');
          }
        } else {
          alert(data.message || 'Gagal menyimpan alamat.');
        }
      })
      .catch(err => {
        console.error('Error saving address:', err);
        btnSaveInlineAddress.removeAttribute('disabled');
        btnSaveInlineAddress.textContent = 'Simpan & Gunakan Alamat Ini';
        alert('Terjadi kesalahan koneksi saat menyimpan alamat.');
      });
    });
  }

  // Initialize map if new address box is open by default (e.g. first time user)
  if (newAddressInlineBox && !newAddressInlineBox.classList.contains('hidden')) {
    setTimeout(() => { initLeafletMap(); }, 300);
  }

  // ==========================================
  // 4. PACKAGE SELECTION WITH RADIO BUTTONS
  // ==========================================
  function filterPackages(category) {
    let firstVisible = null;
    let currentlySelectedVisible = false;

    packageCards.forEach(card => {
      const radio = card.querySelector('input[type="radio"]');
      if (card.dataset.category === category) {
        card.classList.remove('hidden');
        if (!firstVisible) firstVisible = card;
        if (card.classList.contains('selected')) {
          currentlySelectedVisible = true;
        }
      } else {
        card.classList.add('hidden');
        card.classList.remove('selected', 'border-sky-600', 'bg-sky-50/70', 'ring-2', 'ring-sky-500/20');
        if (radio) radio.checked = false;
      }
    });

    if (!currentlySelectedVisible && firstVisible) {
      selectPackage(firstVisible);
    }
  }

  packageCards.forEach(card => {
    card.addEventListener('click', (e) => {
      selectPackage(card);
    });

    const radio = card.querySelector('input[type="radio"]');
    if (radio) {
      radio.addEventListener('change', () => {
        selectPackage(card);
      });
    }
  });

  function selectPackage(card) {
    packageCards.forEach(c => {
      c.classList.remove('selected', 'border-sky-600', 'bg-sky-50/70', 'ring-2', 'ring-sky-500/20');
      const r = c.querySelector('input[type="radio"]');
      if (r) r.checked = false;
    });

    card.classList.add('selected', 'border-sky-600', 'bg-sky-50/70', 'ring-2', 'ring-sky-500/20');
    const radio = card.querySelector('input[type="radio"]');
    if (radio) radio.checked = true;

    const id = card.dataset.id;
    const name = card.dataset.name;
    const price = card.dataset.price;

    if (selectedPackageInput) selectedPackageInput.value = id;
    if (summaryPackageName) summaryPackageName.textContent = name;
    if (summaryPrice) summaryPrice.textContent = formatRupiah(price);
    validateForm();
  }

  // ==========================================
  // 5. DATE & REAL-TIME SLOT AVAILABILITY
  // ==========================================
  if (dateInput) {
    const today = new Date().toISOString().split('T')[0];
    dateInput.min = today;
    if (!dateInput.value) {
      dateInput.value = today;
    }

    dateInput.addEventListener('change', () => {
      fetchSlots(dateInput.value);
    });
    fetchSlots(dateInput.value);
  }

  function fetchSlots(dateStr) {
    if (!slotContainer) return;
    if (slotLoading) slotLoading.classList.remove('hidden');
    slotContainer.innerHTML = '';
    if (selectedTimeInput) selectedTimeInput.value = '';
    if (summaryTime) summaryTime.textContent = 'Belum dipilih';

    fetch(`/api/slots?date=${encodeURIComponent(dateStr)}`)
      .then(res => res.json())
      .then(data => {
        if (slotLoading) slotLoading.classList.add('hidden');
        renderSlots(data);
      })
      .catch(err => {
        console.error('Error fetching slots:', err);
        if (slotLoading) slotLoading.classList.add('hidden');
        slotContainer.innerHTML = '<div class="text-red-500 text-sm col-span-full">Gagal memuat jadwal. Silakan refresh halaman.</div>';
      });
  }

  function renderSlots(data) {
    const { slots, locked, pending, blocked } = data;
    if (!slots || slots.length === 0) {
      slotContainer.innerHTML = '<div class="text-slate-500 text-sm col-span-full">Tidak ada jadwal operasional pada tanggal ini.</div>';
      return;
    }

    slotContainer.innerHTML = '';
    slots.forEach(slot => {
      const isLocked = locked && locked[slot.time_slot];
      const isPending = pending && pending[slot.time_slot];
      const isBlocked = blocked && blocked[slot.time_slot];

      const slotEl = document.createElement('div');
      slotEl.className = 'slot-card';

      if (isLocked) {
        slotEl.classList.add('locked');
        slotEl.innerHTML = `
          <div class="font-bold text-slate-400">${slot.time_slot}</div>
          <span class="slot-badge-locked">⛔ Penuh (Terkonfirmasi)</span>
        `;
      } else if (isBlocked) {
        slotEl.classList.add('locked');
        slotEl.innerHTML = `
          <div class="font-bold text-slate-400">${slot.time_slot}</div>
          <span class="slot-badge-locked">Libur / Tutup</span>
        `;
      } else if (isPending) {
        slotEl.classList.add('available', 'border-amber-300', 'bg-amber-50');
        slotEl.innerHTML = `
          <div class="font-bold text-slate-800">${slot.time_slot}</div>
          <span class="slot-badge-pending">⏳ Antrean Verifikasi</span>
        `;
        slotEl.addEventListener('click', () => {
          selectSlot(slotEl, slot.time_slot);
        });
      } else {
        slotEl.classList.add('available');
        slotEl.innerHTML = `
          <div class="font-bold text-slate-800">${slot.time_slot}</div>
          <div class="text-[11px] text-emerald-600 font-semibold mt-1">✓ Tersedia</div>
        `;
        slotEl.addEventListener('click', () => {
          selectSlot(slotEl, slot.time_slot);
        });
      }

      slotContainer.appendChild(slotEl);
    });
  }

  function selectSlot(element, timeSlot) {
    document.querySelectorAll('.slot-card.available').forEach(el => {
      el.classList.remove('selected');
    });
    element.classList.add('selected');
    if (selectedTimeInput) selectedTimeInput.value = timeSlot;
    if (summaryTime) {
      summaryTime.textContent = `${dateInput.value} pk ${timeSlot} WIB`;
    }
    validateForm();
  }

  // ==========================================
  // 6. VALIDATION & SUBMISSION CHECK
  // ==========================================
  function validateForm() {
    if (!submitBtn) return;
    const hasPackage = Boolean(selectedPackageInput && selectedPackageInput.value);
    const hasSlot = Boolean(selectedTimeInput && selectedTimeInput.value);
    const hasDate = Boolean(dateInput && dateInput.value);
    const hasModel = Boolean(vehicleModelInput && vehicleModelInput.value.trim());
    const hasPlate = Boolean(licensePlateInput && licensePlateInput.value.trim());
    const hasAddress = Boolean(customerAddressInput && customerAddressInput.value.trim());

    if (hasPackage && hasSlot && hasDate && hasModel && hasPlate && hasAddress) {
      submitBtn.removeAttribute('disabled');
      submitBtn.classList.remove('opacity-50', 'cursor-not-allowed');
    } else {
      submitBtn.setAttribute('disabled', 'true');
      submitBtn.classList.add('opacity-50', 'cursor-not-allowed');
    }
  }

  // Initial trigger for category
  const activeVehicleBtn = document.querySelector('.vehicle-btn.active');
  if (activeVehicleBtn) {
    filterPackages(activeVehicleBtn.dataset.category);
  }
});
