import React, { useState, useEffect } from 'react';
import { Eye, EyeOff, Upload, X } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { PrivacyPolicyModal } from '../legal/PrivacyPolicyModal';

interface RegistrationFormData {
  fullName: string;
  email: string;
  username: string;
  password: string;
  confirmPassword: string;
  dni: string;
  phoneNumber: string;
  age: number;
  gender: string;
  weight: number;
  height: number;
  zone: string;
  occupation: string;
  profilePicture?: File | null;
}

interface FormErrors {
  [key: string]: string;
}

interface RegisterFormProps {
  onRegisterSuccess?: () => void;
}

export const RegisterForm: React.FC<RegisterFormProps> = ({ onRegisterSuccess }) => {
  const navigate = useNavigate();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [successMessage, setSuccessMessage] = useState('');
  const [formData, setFormData] = useState<RegistrationFormData>({
    fullName: '',
    email: '',
    username: '',
    password: '',
    confirmPassword: '',
    dni: '',
    phoneNumber: '',
    age: 0,
    gender: '',
    weight: 0,
    height: 0,
    zone: '',
    occupation: '',
    profilePicture: null
  });

  const [errors, setErrors] = useState<FormErrors>({});
  const [touched, setTouched] = useState<{ [key: string]: boolean }>({});
  const [showPassword, setShowPassword] = useState<boolean>(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState<boolean>(false);
  const [profilePreview, setProfilePreview] = useState<string | null>(null);

  // 🔒 Consentimiento de tratamiento de datos personales (Ley N.º 29733)
  const [consentGiven, setConsentGiven] = useState(false);
  const [consentError, setConsentError] = useState('');
  const [showPrivacyModal, setShowPrivacyModal] = useState(false);

  const API_BASE_URL = process.env.NODE_ENV === 'production' 
    ? process.env.REACT_APP_API_URL || 'https://*.com'
    : process.env.REACT_APP_API_URL || 'http://localhost:8000';

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

  useEffect(() => {
    let timeoutId: NodeJS.Timeout;
    
    if (successMessage) {
      timeoutId = setTimeout(() => {
        if (onRegisterSuccess) {
          onRegisterSuccess();
        } else {
          navigate('/login');
        }
      }, 2000);
    }
  
    return () => {
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
    };
  }, [successMessage, navigate, onRegisterSuccess]);

  useEffect(() => {
    return () => {
      if (profilePreview) {
        URL.revokeObjectURL(profilePreview);
      }
    };
  }, [profilePreview]);

  const handleKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
    const { key, currentTarget } = e;
    const name = currentTarget.name;
    
    if (name === 'fullName') {
      if (/[0-9]/.test(key)) {
        e.preventDefault();
      }
    }
    
    if (name === 'dni' || name === 'phoneNumber' || name === 'height') {
      if (!/[0-9]/.test(key) && key !== 'Backspace' && key !== 'Delete' && key !== 'ArrowLeft' && key !== 'ArrowRight' && key !== 'Tab') {
        e.preventDefault();
      }
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
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

    if (profilePreview) {
      URL.revokeObjectURL(profilePreview);
    }
    const previewUrl = URL.createObjectURL(file);
    setProfilePreview(previewUrl);
    
    setFormData(prev => ({ ...prev, profilePicture: file }));
    setErrors(prev => ({ ...prev, profilePicture: '' }));
  };

  const handleRemovePhoto = () => {
    if (profilePreview) {
      URL.revokeObjectURL(profilePreview);
      setProfilePreview(null);
    }
    setFormData(prev => ({ ...prev, profilePicture: null }));
    setErrors(prev => ({ ...prev, profilePicture: '' }));
  };

  const validateField = (name: string, value: string | number | File | null | undefined): string => {
    const fieldValue = value === undefined ? '' : value;
    
    switch (name) {
      case 'fullName':
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
      case 'username':
        if (!fieldValue) return 'El usuario es requerido';
        if (!/(?=.*[A-Z])(?=.*[a-z])(?=.*\d)[A-Za-z\d]{6,20}$/.test(fieldValue.toString())) {
          return 'El usuario debe tener entre 6 y 20 caracteres, al menos una mayúscula, una minúscula y un número';
        }
        break;
      case 'password':
        if (!fieldValue) return 'La contraseña es requerida';
        if (fieldValue.toString().length < 8) {
          return 'La contraseña debe tener al menos 8 caracteres';
        }
        if (!/(?=.*[a-z])/.test(fieldValue.toString())) {
          return 'La contraseña debe contener al menos una letra minúscula';
        }
        if (!/(?=.*[A-Z])/.test(fieldValue.toString())) {
          return 'La contraseña debe contener al menos una letra mayúscula';
        }
        if (!/(?=.*\d)/.test(fieldValue.toString())) {
          return 'La contraseña debe contener al menos un número';
        }
        if (!/(?=.*[@$!%*?&])/.test(fieldValue.toString())) {
          return 'La contraseña debe contener al menos un carácter especial (@$!%*?&)';
        }
        break;
      case 'confirmPassword':
        if (!fieldValue) return 'Debe confirmar la contraseña';
        if (fieldValue !== formData.password) {
          return 'Las contraseñas no coinciden';
        }
        break;
      case 'dni':
        if (!fieldValue) return 'El DNI es requerido';
        if (!/^\d{8}$/.test(fieldValue.toString())) {
          return 'El DNI debe tener exactamente 8 dígitos numéricos';
        }
        break;
      case 'phoneNumber':
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
      case 'profilePicture':
        if (fieldValue instanceof File) {
          if (fieldValue.size > 5 * 1024 * 1024) {
            return 'La imagen no debe superar los 5MB';
          }
        }
        break;
    }
    return '';
  };

  const validateAllFields = (): boolean => {
    const newErrors: FormErrors = {};
    const newTouched: { [key: string]: boolean } = {};
    
    const fieldsToValidate = [
      'fullName', 'email', 'username', 'password', 'confirmPassword',
      'dni', 'phoneNumber', 'age', 'gender', 'weight', 'height', 'zone', 'occupation'
    ];
    
    let isValid = true;
    
    fieldsToValidate.forEach(fieldName => {
      newTouched[fieldName] = true;
      const fieldValue = formData[fieldName as keyof RegistrationFormData];
      const valueForValidation = fieldValue === undefined ? '' : fieldValue;
      const error = validateField(fieldName, valueForValidation);
      
      if (error) {
        newErrors[fieldName] = error;
        isValid = false;
      }
    });
    
    if (formData.profilePicture) {
      const photoError = validateField('profilePicture', formData.profilePicture);
      if (photoError) {
        newErrors.profilePicture = photoError;
        isValid = false;
      }
    }
    
    setTouched(newTouched);
    setErrors(newErrors);
    
    return isValid;
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    
    if (name === 'dni' || name === 'phoneNumber' || name === 'height') {
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

  // 🔒 Maneja el cambio del checkbox de consentimiento y limpia su error al marcarlo
  const handleConsentChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setConsentGiven(e.target.checked);
    if (e.target.checked) {
      setConsentError('');
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // 🔒 Guard de consentimiento — no continúa si no fue marcado
    if (!consentGiven) {
      setConsentError('Debes autorizar el tratamiento de tus datos personales para poder registrarte.');
      return;
    }
    
    const isFormValid = validateAllFields();
    
    if (!isFormValid) {
      alert('Por favor, complete todos los campos requeridos correctamente.');
      return;
    }
    
    setIsSubmitting(true);

    try {
      console.log('📤 Enviando registro...');
      
      const formDataToSend = new FormData();
      
      formDataToSend.append('fullName', formData.fullName);
      formDataToSend.append('email', formData.email);
      formDataToSend.append('username', formData.username);
      formDataToSend.append('password', formData.password);
      formDataToSend.append('dni', formData.dni);
      formDataToSend.append('phoneNumber', formData.phoneNumber);
      formDataToSend.append('age', formData.age.toString());
      formDataToSend.append('gender', formData.gender);
      formDataToSend.append('weight', formData.weight.toString());
      formDataToSend.append('height', formData.height.toString());
      formDataToSend.append('zone', formData.zone);
      formDataToSend.append('occupation', formData.occupation || '');
      
      if (formData.profilePicture) {
        formDataToSend.append('profile_picture', formData.profilePicture);
        console.log('📸 Foto incluida en registro');
      }

      console.log('🚀 Enviando a:', `${API_BASE_URL}/api/register`);
      
      const response = await fetch(`${API_BASE_URL}/api/register`, {
        method: 'POST',
        body: formDataToSend
      });

      const data = await response.json();

      if (!response.ok) {
        console.error('❌ Error del servidor:', data);
        
        if (data.detail) {
          if (data.detail.includes("usuario") || data.detail.includes("username")) {
            setErrors(prev => ({ ...prev, username: data.detail }));
          } else if (data.detail.includes("correo") || data.detail.includes("email")) {
            setErrors(prev => ({ ...prev, email: data.detail }));
          } else if (data.detail.includes("DNI") || data.detail.includes("dni")) {
            setErrors(prev => ({ ...prev, dni: data.detail }));
          } else if (data.detail.includes("teléfono") || data.detail.includes("phone")) {
            setErrors(prev => ({ ...prev, phoneNumber: data.detail }));
          } else if (data.detail.includes("imagen") || data.detail.includes("foto")) {
            setErrors(prev => ({ ...prev, profilePicture: data.detail }));
          } else {
            alert(`Error: ${data.detail}`);
          }
        } else {
          alert('Error desconocido del servidor');
        }
        
        setIsSubmitting(false);
        return;
      }

      console.log('✅ Registro exitoso:', data);
      setSuccessMessage(data.message || '¡Usuario registrado exitosamente! Redirigiendo al login...');

    } catch (error) {
      console.error('❌ Error de red:', error);
      alert('Error de conexión. Verifica que el servidor esté ejecutándose en http://localhost:8000');
    } finally {
      setIsSubmitting(false);
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

  return (
    <div className="w-full max-w-6xl mx-auto">
      <div className="bg-white/95 backdrop-blur-xl rounded-2xl shadow-2xl border border-emerald-100/50 overflow-hidden">
        
        {/* Header compacto */}
        <div className="bg-gradient-to-r from-emerald-600 to-teal-700 p-4 text-center">
          <h2 className="text-2xl font-bold text-white">Registro de Usuario</h2>
          <p className="text-emerald-100 text-sm mt-1">Completa tus datos para comenzar</p>
        </div>

        {/* Formulario */}
        <form onSubmit={handleSubmit} className="p-6">
          
          {/* Success message */}
          {successMessage && (
            <div className="mb-4 p-3 bg-emerald-50 border-l-4 border-emerald-500 rounded-lg">
              <div className="flex items-center gap-2">
                <span className="text-emerald-500 text-lg">✓</span>
                <p className="text-emerald-700 text-sm font-medium">{successMessage}</p>
              </div>
            </div>
          )}

          <div className="space-y-4">
            
            {/* Foto de perfil */}
            <div className="bg-gradient-to-br from-slate-50 to-emerald-50 p-4 rounded-xl border border-emerald-100 flex items-center gap-5">
              <div className="flex-shrink-0">
                <div className="relative">
                  <div className="w-20 h-20 rounded-full overflow-hidden border-3 border-white shadow-lg bg-gradient-to-br from-emerald-100 to-teal-100">
                    {profilePreview ? (
                      <img src={profilePreview} alt="Preview" className="w-full h-full object-cover" />
                    ) : (
                      <div className="w-full h-full flex flex-col items-center justify-center text-slate-400">
                        <Upload size={28} />
                      </div>
                    )}
                  </div>
                  
                  <div className="absolute -bottom-1 -right-1 flex gap-1">
                    <label className="cursor-pointer">
                      <input type="file" accept="image/jpeg,image/png,image/gif,image/webp" onChange={handleFileSelect} className="hidden" />
                      <div className="w-8 h-8 bg-emerald-500 text-white rounded-full flex items-center justify-center shadow-lg hover:bg-emerald-600 transition-all">
                        <Upload size={16} />
                      </div>
                    </label>
                    
                    {profilePreview && (
                      <button type="button" onClick={handleRemovePhoto} className="w-8 h-8 bg-rose-500 text-white rounded-full flex items-center justify-center shadow-lg hover:bg-rose-600 transition-all">
                        <X size={16} />
                      </button>
                    )}
                  </div>
                </div>
              </div>

              <div className="flex-1">
                <p className="text-sm font-semibold text-slate-700">Foto de Perfil <span className="text-slate-400 font-normal">(Opcional)</span></p>
                <p className="text-xs text-slate-500 mt-0.5">JPG, PNG, GIF, WebP • Máximo 5MB</p>
              </div>
            </div>

            {/* 🔥 GRID DE 4 COLUMNAS - NUEVO ORDEN CON NIVEL EDUCATIVO ARRIBA */}
            <div className="grid grid-cols-4 gap-3">
              
              {/* Fila 1: Nombre completo (2 cols) + Email + Username */}
              <div className="col-span-2">
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Nombre Completo <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  name="fullName"
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
                  placeholder="Tu nombre completo"
                  value={formData.fullName}
                  onChange={handleChange}
                  onBlur={handleBlur}
                  onKeyPress={handleKeyPress}
                  required
                />
                {renderError('fullName')}
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
                  Usuario <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  name="username"
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
                  placeholder="Usuario123"
                  value={formData.username}
                  onChange={handleChange}
                  onBlur={handleBlur}
                  required
                />
                {renderError('username')}
              </div>

              {/* Fila 2: DNI + Teléfono + Password + Confirmar */}
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
                  name="phoneNumber"
                  maxLength={9}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
                  placeholder="987654321"
                  value={formData.phoneNumber}
                  onChange={handleChange}
                  onBlur={handleBlur}
                  onKeyPress={handleKeyPress}
                  required
                />
                {renderError('phoneNumber')}
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Contraseña <span className="text-rose-500">*</span>
                </label>
                <div className="relative">
                  <input
                    type={showPassword ? "text" : "password"}
                    name="password"
                    className="w-full px-3 py-2 pr-10 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
                    placeholder="••••••••"
                    value={formData.password}
                    onChange={handleChange}
                    onBlur={handleBlur}
                    required
                  />
                  <button
                    type="button"
                    className="absolute right-2 top-1/2 transform -translate-y-1/2 text-slate-400 hover:text-emerald-600"
                    onClick={() => setShowPassword(!showPassword)}
                  >
                    {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
                {renderError('password')}
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Confirmar <span className="text-rose-500">*</span>
                </label>
                <div className="relative">
                  <input
                    type={showConfirmPassword ? "text" : "password"}
                    name="confirmPassword"
                    className="w-full px-3 py-2 pr-10 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
                    placeholder="••••••••"
                    value={formData.confirmPassword}
                    onChange={handleChange}
                    onBlur={handleBlur}
                    required
                  />
                  <button
                    type="button"
                    className="absolute right-2 top-1/2 transform -translate-y-1/2 text-slate-400 hover:text-emerald-600"
                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                  >
                    {showConfirmPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
                {renderError('confirmPassword')}
              </div>

              {/* Fila 3: Edad + Género + Peso + Altura */}
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

              {/* 🔥 Fila 4: Zona (1 col) + Nivel Educativo (3 cols) - NIVEL EDUCATIVO AHORA ARRIBA */}
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
            </div>

            {/* 🔒 Checkbox de consentimiento — tratamiento de datos personales (Ley N.º 29733) */}
            <div className="bg-gradient-to-br from-slate-50 to-emerald-50 p-4 rounded-xl border border-emerald-100">
              <label className="flex items-start gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  name="consent"
                  checked={consentGiven}
                  onChange={handleConsentChange}
                  className="mt-0.5 h-4 w-4 flex-shrink-0 rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
                />
                <span className="text-xs text-slate-600 leading-relaxed">
                  Autorizo el tratamiento de mis datos personales, incluyendo datos de salud
                  (síntomas, edad, peso), para generar recomendaciones personalizadas y para el
                  uso de mi retroalimentación de forma agregada y/o anonimizada en la mejora del
                  sistema. He leído la{' '}
                  <button
                    type="button"
                    onClick={() => setShowPrivacyModal(true)}
                    className="text-emerald-600 hover:text-emerald-700 font-semibold hover:underline"
                  >
                    Política de Privacidad
                  </button>
                  . <span className="text-rose-500">*</span>
                </span>
              </label>
              {consentError && (
                <div className="text-xs text-rose-600 mt-2">
                  {consentError}
                </div>
              )}
            </div>

            {/* Botón de submit */}
            <button
              type="submit"
              disabled={isSubmitting || !consentGiven}
              className={`w-full bg-gradient-to-r from-emerald-600 to-teal-700 text-white font-bold py-3 rounded-xl hover:from-emerald-700 hover:to-teal-800 text-base shadow-lg hover:shadow-xl ${
                isSubmitting || !consentGiven ? 'opacity-50 cursor-not-allowed' : 'hover:scale-[1.01] transition-all'
              }`}
            >
              {isSubmitting ? 'Registrando...' : 'Registrarse'}
            </button>
          </div>
        </form>

        {/* Footer */}
        <div className="bg-slate-50 px-6 py-3 border-t border-slate-100">
          <div className="flex items-center justify-center gap-2 text-sm">
            <span className="text-slate-600">¿Ya tienes cuenta?</span>
            <a href="/login" className="text-emerald-600 hover:text-emerald-700 font-semibold hover:underline">
              Inicia sesión
            </a>
          </div>
        </div>
      </div>

      <PrivacyPolicyModal isOpen={showPrivacyModal} onClose={() => setShowPrivacyModal(false)} />
    </div>
  );
};

export default RegisterForm;