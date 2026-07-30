// components/auth/EditProfilePage.tsx
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Upload, X, Eye, EyeOff } from 'lucide-react';
import { API_BASE_URL } from '../../App';

interface UserProfile {
  id: string;
  full_name: string;
  email: string;
  username: string;
  dni: string;
  phone_number: string;
  age: number;
  gender: string;
  weight: number;
  height: number;
  zone: string;
  occupation: string;
  profile_picture_url: string | null;
  created_at: string;
  role: string;
}

interface FormErrors {
  [key: string]: string;
}

const occupationOptions = [
  "Sin nivel educativo/sin instrucción",
  "Preescolar",
  "Primaria incompleta",
  "Primaria completa",
  "Secundaria incompleta",
  "Secundaria completa",
  "Técnica superior incompleta",
  "Técnica superior completa",
  "Universitaria incompleta",
  "Universitaria completa",
  "Maestría/doctorado"
];

export const EditProfilePage = () => {
  const navigate = useNavigate();
  const [userProfile, setUserProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [profilePicture, setProfilePicture] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [errors, setErrors] = useState<FormErrors>({});
  const [touched, setTouched] = useState<{ [key: string]: boolean }>({});

  // Form data state
  const [formData, setFormData] = useState({
    full_name: '',
    email: '',
    dni: '',
    phone_number: '',
    age: 0,
    gender: '',
    weight: 0,
    height: 0,
    zone: '',
    occupation: ''
  });

  useEffect(() => {
    const loadUserProfile = async () => {
      try {
        const auth = localStorage.getItem('auth');
        if (!auth) {
          navigate('/login');
          return;
        }

        const parsed = JSON.parse(auth);
        const token = parsed.token;
        const username = parsed.user?.username;

        if (!token || !username) {
          navigate('/login');
          return;
        }

        const response = await fetch(`${API_BASE_URL}/api/user/${username}`, {
          headers: {
            'Authorization': `Bearer ${token}`,
          },
        });

        if (!response.ok) {
          throw new Error('No se pudo cargar el perfil');
        }

        const data = await response.json();
        setUserProfile(data);
        setPreviewUrl(data.profile_picture_url);
        
        // Inicializar formData con los datos del usuario
        setFormData({
          full_name: data.full_name,
          email: data.email,
          dni: data.dni,
          phone_number: data.phone_number,
          age: data.age,
          gender: data.gender,
          weight: data.weight,
          height: data.height,
          zone: data.zone,
          occupation: data.occupation || ''
        });
      } catch (error) {
        setError('Error al cargar el perfil. Por favor, inténtalo de nuevo.');
        console.error('Error loading profile:', error);
      } finally {
        setLoading(false);
      }
    };

    loadUserProfile();
  }, [navigate]);

  useEffect(() => {
    return () => {
      if (previewUrl && previewUrl.startsWith('blob:')) {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, [previewUrl]);

  const handleKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
    const { key, currentTarget } = e;
    const name = currentTarget.name;
    
    if (name === 'full_name') {
      if (/[0-9]/.test(key)) {
        e.preventDefault();
      }
    }
    
    if (name === 'dni' || name === 'phone_number' || name === 'height') {
      if (!/[0-9]/.test(key) && key !== 'Backspace' && key !== 'Delete' && key !== 'ArrowLeft' && key !== 'ArrowRight' && key !== 'Tab') {
        e.preventDefault();
      }
    }
  };

  const handleProfilePictureChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const validTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp'];
    if (!validTypes.includes(file.type)) {
      alert('Solo se permiten imágenes JPG, PNG, GIF o WebP');
      return;
    }

    if (file.size > 5 * 1024 * 1024) {
      alert('La imagen no debe superar los 5MB');
      return;
    }

    if (previewUrl && previewUrl.startsWith('blob:')) {
      URL.revokeObjectURL(previewUrl);
    }
    const newPreviewUrl = URL.createObjectURL(file);
    setPreviewUrl(newPreviewUrl);
    setProfilePicture(file);
    setErrors(prev => ({ ...prev, profilePicture: '' }));
  };

  const handleRemovePhoto = () => {
    if (previewUrl && previewUrl.startsWith('blob:')) {
      URL.revokeObjectURL(previewUrl);
    }
    setPreviewUrl(userProfile?.profile_picture_url || null);
    setProfilePicture(null);
    setErrors(prev => ({ ...prev, profilePicture: '' }));
  };

  const validateField = (name: string, value: string | number): string => {
    const fieldValue = value === undefined ? '' : value;
    
    switch (name) {
      case 'full_name':
        if (!fieldValue) return 'El nombre completo es requerido';
        if (fieldValue.toString().length < 2) return 'El nombre completo debe tener al menos 2 caracteres';
        if (!/^[A-Za-zÁáÉéÍíÓóÚúÑñ ]+$/.test(fieldValue.toString())) {
          return 'El nombre completo solo puede contener letras y espacios';
        }
        break;
      case 'email':
        if (!fieldValue) return 'El correo electrónico es requerido';
        if (!/^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i.test(fieldValue.toString())) {
          return 'Ingrese un correo electrónico válido';
        }
        break;
      case 'dni':
        if (!fieldValue) return 'El DNI es requerido';
        if (!/^\d{8}$/.test(fieldValue.toString())) {
          return 'El DNI debe tener exactamente 8 dígitos numéricos';
        }
        break;
      case 'phone_number':
        if (!fieldValue) return 'El número de teléfono es requerido';
        if (!/^9\d{8}$/.test(fieldValue.toString())) {
          return 'El número debe empezar con 9 y tener 9 dígitos numéricos';
        }
        break;
      case 'age':
        const ageNum = Number(fieldValue);
        if (!fieldValue || ageNum === 0) return 'La edad es requerida';
        if (ageNum < 1 || ageNum > 120) {
          return 'La edad debe estar entre 1 y 120 años';
        }
        break;
      case 'gender':
        if (!fieldValue) return 'El género es requerido';
        break;
      case 'weight':
        const weightNum = Number(fieldValue);
        if (!fieldValue || weightNum === 0) return 'El peso es requerido';
        if (weightNum < 2) return 'El peso mínimo debe ser 2 kg';
        if (weightNum > 200) return 'El peso máximo debe ser 200 kg';
        break;
      case 'height':
        if (!fieldValue || Number(fieldValue) === 0) return 'La altura es requerida';
        const heightStr = fieldValue.toString();
        if (!/^\d{2,3}$/.test(heightStr)) {
          return 'La altura debe ser un número entero en centímetros (30-220)';
        }
        const heightNum = Number(fieldValue);
        if (heightNum < 30 || heightNum > 220) {
          return 'La altura debe estar entre 30 y 220 cm';
        }
        break;
      case 'zone':
        if (!fieldValue) return 'La zona es requerida';
        if (!['rural', 'urbana'].includes(fieldValue.toString().toLowerCase())) {
          return 'La zona debe ser rural o urbana';
        }
        break;
      case 'occupation':
        if (!fieldValue) return 'El nivel educativo es requerido';
        break;
    }
    return '';
  };

  const validateAllFields = (): boolean => {
    const newErrors: FormErrors = {};
    const newTouched: { [key: string]: boolean } = {};
    
    const fieldsToValidate = [
      'full_name', 'email', 'dni', 'phone_number', 'age', 
      'gender', 'weight', 'height', 'zone', 'occupation'
    ];
    
    let isValid = true;
    
    fieldsToValidate.forEach(fieldName => {
      newTouched[fieldName] = true;
      const fieldValue = formData[fieldName as keyof typeof formData];
      const valueForValidation = fieldValue === undefined ? '' : fieldValue;
      const error = validateField(fieldName, valueForValidation);
      
      if (error) {
        newErrors[fieldName] = error;
        isValid = false;
      }
    });
    
    setTouched(newTouched);
    setErrors(newErrors);
    
    return isValid;
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    
    if (name === 'dni' || name === 'phone_number' || name === 'height') {
      if (!/^\d*$/.test(value)) {
        return;
      }
    }
    
    setFormData(prev => ({ ...prev, [name]: value }));
    setTouched(prev => ({ ...prev, [name]: true }));
    const error = validateField(name, value);
    setErrors(prev => ({ ...prev, [name]: error }));
  };

  const handleBlur = (e: React.FocusEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setTouched(prev => ({ ...prev, [name]: true }));
    const error = validateField(name, value);
    setErrors(prev => ({ ...prev, [name]: error }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    const isFormValid = validateAllFields();
    
    if (!isFormValid) {
      alert('Por favor, complete todos los campos requeridos correctamente.');
      return;
    }
    
    setSaving(true);
    setError(null);
    setSuccess(null);

    try {
      const auth = localStorage.getItem('auth');
      if (!auth || !userProfile) return;

      const parsed = JSON.parse(auth);
      const token = parsed.token;
      const username = userProfile.username;

      const formDataToSend = new FormData();
      
      formDataToSend.append('full_name', formData.full_name);
      formDataToSend.append('email', formData.email);
      formDataToSend.append('dni', formData.dni);
      formDataToSend.append('phone_number', formData.phone_number);
      formDataToSend.append('age', formData.age.toString());
      formDataToSend.append('gender', formData.gender);
      formDataToSend.append('weight', formData.weight.toString());
      formDataToSend.append('height', formData.height.toString());
      formDataToSend.append('zone', formData.zone);
      formDataToSend.append('occupation', formData.occupation || '');
      
      if (profilePicture) {
        formDataToSend.append('profile_picture', profilePicture);
      }

      const response = await fetch(`${API_BASE_URL}/api/user/${username}/update`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
        body: formDataToSend,
      });

      const data = await response.json();

      if (!response.ok) {
        if (data.detail) {
          if (data.detail.includes("correo") || data.detail.includes("email")) {
            setErrors(prev => ({ ...prev, email: data.detail }));
          } else if (data.detail.includes("DNI") || data.detail.includes("dni")) {
            setErrors(prev => ({ ...prev, dni: data.detail }));
          } else if (data.detail.includes("teléfono") || data.detail.includes("phone")) {
            setErrors(prev => ({ ...prev, phone_number: data.detail }));
          } else if (data.detail.includes("imagen") || data.detail.includes("foto")) {
            setErrors(prev => ({ ...prev, profilePicture: data.detail }));
          } else {
            setError(`Error: ${data.detail}`);
          }
        } else {
          setError('Error desconocido del servidor');
        }
        setSaving(false);
        return;
      }

      setUserProfile(data.user);
      setSuccess('Perfil actualizado exitosamente');
      
      if (data.user.profile_picture_url) {
        setPreviewUrl(data.user.profile_picture_url);
      }
      
      setProfilePicture(null);
      
      setTimeout(() => {
        window.location.reload();
      }, 1000);

    } catch (error) {
      setError(error instanceof Error ? error.message : 'Error al actualizar el perfil');
    } finally {
      setSaving(false);
    }
  };

  const renderError = (fieldName: string) => {
    if (touched[fieldName] && errors[fieldName]) {
      return (
        <div className="text-xs text-rose-600 mt-1">
          {errors[fieldName]}
        </div>
      );
    }
    return null;
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-emerald-50 flex items-center justify-center">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-emerald-500 border-t-transparent rounded-full animate-spin mx-auto"></div>
          <p className="mt-4 text-slate-600 text-lg">Cargando perfil...</p>
        </div>
      </div>
    );
  }

  if (!userProfile) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-emerald-50 flex items-center justify-center">
        <div className="text-center">
          <p className="text-slate-600 text-lg mb-4">No se pudo cargar el perfil.</p>
          <button
            onClick={() => navigate('/chat')}
            className="px-6 py-3 bg-emerald-500 text-white rounded-xl hover:bg-emerald-600 transition-all shadow-md hover:shadow-lg"
          >
            Volver al Chat
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full max-w-5xl mx-auto px-4">
      <div className="bg-white/95 backdrop-blur-xl rounded-2xl shadow-2xl border border-emerald-100/50 overflow-hidden">
        
        {/* Header compacto */}
        <div className="bg-gradient-to-r from-emerald-600 to-teal-700 p-3 text-center">
          <h2 className="text-xl font-bold text-white">Editar Perfil</h2>
          <p className="text-emerald-100 text-xs mt-1">Actualiza tu información personal</p>
        </div>

        {/* Formulario */}
        <form onSubmit={handleSubmit} className="p-4">
          
          {/* Success/Error messages */}
          {error && (
            <div className="mb-4 p-3 bg-rose-50 border-l-4 border-rose-500 rounded-lg">
              <div className="flex items-center gap-2">
                <span className="text-rose-500 text-lg">✕</span>
                <p className="text-rose-700 text-sm font-medium">{error}</p>
              </div>
            </div>
          )}

          {success && (
            <div className="mb-4 p-3 bg-emerald-50 border-l-4 border-emerald-500 rounded-lg">
              <div className="flex items-center gap-2">
                <span className="text-emerald-500 text-lg">✓</span>
                <p className="text-emerald-700 text-sm font-medium">{success}</p>
              </div>
            </div>
          )}

          <div className="space-y-3">
            
            {/* Foto de perfil */}
            <div className="bg-gradient-to-br from-slate-50 to-emerald-50 p-3 rounded-xl border border-emerald-100 flex items-center gap-3">
              <div className="flex-shrink-0">
                <div className="relative">
                  <div className="w-16 h-16 rounded-full overflow-hidden border-2 border-white shadow-md bg-gradient-to-br from-emerald-100 to-teal-100">
                    {previewUrl ? (
                      <img 
                        src={previewUrl} 
                        alt="Preview" 
                        className="w-full h-full object-cover"
                        onError={(e) => {
                          const target = e.target as HTMLImageElement;
                          target.style.display = 'none';
                          const fallbackDiv = target.parentNode as HTMLDivElement;
                          fallbackDiv.className = 'w-16 h-16 bg-gradient-to-br from-emerald-400 to-teal-500 rounded-full flex items-center justify-center text-white font-bold text-xl border-2 border-white shadow-md';
                          fallbackDiv.innerHTML = userProfile.full_name.charAt(0).toUpperCase();
                        }}
                      />
                    ) : (
                      <div className="w-full h-full flex flex-col items-center justify-center text-slate-400">
                        <Upload size={24} />
                      </div>
                    )}
                  </div>
                  
                  <div className="absolute -bottom-0.5 -right-0.5 flex gap-1">
                    <label className="cursor-pointer">
                      <input 
                        type="file" 
                        accept="image/jpeg,image/png,image/gif,image/webp" 
                        onChange={handleProfilePictureChange} 
                        className="hidden" 
                      />
                      <div className="w-6 h-6 bg-emerald-500 text-white rounded-full flex items-center justify-center shadow-md hover:bg-emerald-600 transition-all">
                        <Upload size={14} />
                      </div>
                    </label>
                    
                    {profilePicture && (
                      <button 
                        type="button" 
                        onClick={handleRemovePhoto} 
                        className="w-6 h-6 bg-rose-500 text-white rounded-full flex items-center justify-center shadow-md hover:bg-rose-600 transition-all"
                      >
                        <X size={14} />
                      </button>
                    )}
                  </div>
                </div>
              </div>

              <div className="flex-1">
                <p className="text-xs font-semibold text-slate-700">Foto de Perfil <span className="text-slate-400 font-normal">(Opcional)</span></p>
                <p className="text-xs text-slate-500 mt-0.5">JPG, PNG, GIF, WebP • Máx 5MB</p>
              </div>
            </div>

            {/* GRID DE 4 COLUMNAS - EXACTO AL REGISTERFORM */}
            <div className="grid grid-cols-4 gap-2">
              
              {/* Fila 1: Nombre completo (2 cols) + Email + Username */}
              <div className="col-span-2">
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Nombre Completo <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  name="full_name"
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
                  placeholder="Tu nombre completo"
                  value={formData.full_name}
                  onChange={handleChange}
                  onBlur={handleBlur}
                  onKeyPress={handleKeyPress}
                  required
                />
                {renderError('full_name')}
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Correo <span className="text-rose-500">*</span>
                </label>
                <input
                  type="email"
                  name="email"
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
                  placeholder="tu@email.com"
                  value={formData.email}
                  onChange={handleChange}
                  onBlur={handleBlur}
                  required
                />
                {renderError('email')}
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Usuario
                </label>
                <input
                  type="text"
                  value={userProfile.username}
                  disabled
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-slate-50 text-slate-500 cursor-not-allowed"
                />
                <p className="text-xs text-slate-400 mt-0.5">No se puede modificar</p>
              </div>

              {/* Fila 2: DNI + Teléfono + Edad + Género */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  DNI <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  name="dni"
                  maxLength={8}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
                  placeholder="12345678"
                  value={formData.dni}
                  onChange={handleChange}
                  onBlur={handleBlur}
                  onKeyPress={handleKeyPress}
                  required
                />
                {renderError('dni')}
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Teléfono <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  name="phone_number"
                  maxLength={9}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
                  placeholder="987654321"
                  value={formData.phone_number}
                  onChange={handleChange}
                  onBlur={handleBlur}
                  onKeyPress={handleKeyPress}
                  required
                />
                {renderError('phone_number')}
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Edad <span className="text-rose-500">*</span>
                </label>
                <input
                  type="number"
                  name="age"
                  min="1"
                  max="120"
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
                  placeholder="25"
                  value={formData.age || ''}
                  onChange={handleChange}
                  onBlur={handleBlur}
                  required
                />
                {renderError('age')}
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Género <span className="text-rose-500">*</span>
                </label>
                <select
                  name="gender"
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
                  value={formData.gender}
                  onChange={handleChange}
                  onBlur={handleBlur}
                  required
                >
                  <option value="">Seleccionar...</option>
                  <option value="masculino">Masculino</option>
                  <option value="femenino">Femenino</option>
                  <option value="otro">Otro</option>
                </select>
                {renderError('gender')}
              </div>

              {/* Fila 3: Peso + Altura + Zona + Espacio vacío */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Peso (kg) <span className="text-rose-500">*</span>
                </label>
                <input
                  type="number"
                  name="weight"
                  min="2"
                  max="200"
                  step="0.1"
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
                  placeholder="70"
                  value={formData.weight || ''}
                  onChange={handleChange}
                  onBlur={handleBlur}
                  required
                />
                {renderError('weight')}
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Altura (cm) <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  name="height"
                  maxLength={3}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
                  placeholder="172"
                  value={formData.height || ''}
                  onChange={handleChange}
                  onBlur={handleBlur}
                  onKeyPress={handleKeyPress}
                  required
                />
                {renderError('height')}
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Zona <span className="text-rose-500">*</span>
                </label>
                <select
                  name="zone"
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
                  value={formData.zone}
                  onChange={handleChange}
                  onBlur={handleBlur}
                  required
                >
                  <option value="">Seleccionar...</option>
                  <option value="rural">Rural</option>
                  <option value="urbana">Urbana</option>
                </select>
                {renderError('zone')}
              </div>

              {/* Espacio vacío en la cuarta columna */}
              <div></div>

              {/* Fila 4: Nivel Educativo (3 cols) + Espacio vacío */}
              <div className="col-span-3">
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Nivel Educativo <span className="text-rose-500">*</span>
                </label>
                <select
                  name="occupation"
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
                  value={formData.occupation}
                  onChange={handleChange}
                  onBlur={handleBlur}
                  required
                >
                  <option value="">Seleccionar nivel educativo...</option>
                  {occupationOptions.map((option, index) => (
                    <option key={index} value={option}>{option}</option>
                  ))}
                </select>
                {renderError('occupation')}
              </div>

              {/* Espacio vacío en la cuarta columna */}
              <div></div>
            </div>

            {/* Botones */}
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => navigate('/chat')}
                className="flex-1 px-4 py-2.5 border-2 border-slate-300 text-slate-700 rounded-xl hover:bg-slate-50 transition-all text-sm font-medium shadow-sm hover:shadow"
                disabled={saving}
              >
                Cancelar
              </button>
              
              <button
                type="submit"
                disabled={saving}
                className={`flex-1 bg-gradient-to-r from-emerald-600 to-teal-700 text-white font-bold py-2.5 rounded-xl hover:from-emerald-700 hover:to-teal-800 text-sm shadow-lg hover:shadow-xl ${
                  saving ? 'opacity-50 cursor-not-allowed' : 'hover:scale-[1.01] transition-all'
                }`}
              >
                {saving ? 'Guardando...' : 'Guardar Cambios'}
              </button>
            </div>
          </div>
        </form>

        {/* Footer */}
        <div className="bg-slate-50 px-4 py-2 border-t border-slate-100">
          <div className="flex items-center justify-center gap-2 text-xs">
            <span className="text-slate-600">¿Necesitas ayuda?</span>
            <button
              onClick={() => navigate('/chat')}
              className="text-emerald-600 hover:text-emerald-700 font-semibold hover:underline"
            >
              Volver al chat
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};