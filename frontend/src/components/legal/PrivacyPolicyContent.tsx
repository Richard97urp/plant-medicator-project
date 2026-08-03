import React from 'react';

// ⚠️ Antes de publicar en producción, completa los placeholders entre [corchetes]
// y verifica la política real de retención de datos del proveedor de LLM (Groq)
// en la sección 5 antes de dejar ese texto como definitivo.

export const PrivacyPolicyContent: React.FC = () => {
  return (
    <div className="space-y-6">
      <p className="text-xs text-slate-400">Última actualización: [dd/mm/aaaa]</p>

      <p>
        Este documento describe cómo se recopilan, usan y protegen los datos personales de
        las personas usuarias registradas en la plataforma web (en adelante, &quot;la Plataforma&quot;).
        Aplica a toda persona que se registre y utilice la Plataforma, independientemente de si
        su información es usada en el estudio de tesis descrito en los documentos de
        consentimiento informado correspondientes.
      </p>

      <section>
        <h3 className="text-base font-bold text-emerald-700 mb-2">1. Responsable del tratamiento</h3>
        <p><span className="font-semibold">Responsable:</span> Richard Mauri Ñope Giraldo</p>
        <p><span className="font-semibold">Institución:</span> Universidad Ricardo Palma, Escuela Profesional de Ingeniería Mecatrónica</p>
        <p><span className="font-semibold">Contacto para consultas o ejercicio de derechos:</span> 201511342@urp.edu.pe</p>
      </section>

      <section>
        <h3 className="text-base font-bold text-emerald-700 mb-2">2. Datos que se recopilan</h3>
        <ul className="list-disc pl-5 space-y-1">
          <li><span className="font-semibold">Datos de cuenta:</span> nombre completo, correo electrónico, nombre de usuario, DNI, número de teléfono, contraseña (almacenada de forma cifrada).</li>
          <li><span className="font-semibold">Datos personales de salud:</span> edad, peso, talla, género, zona de residencia, ocupación.</li>
          <li><span className="font-semibold">Datos de la consulta:</span> síntomas, duración, intensidad, causas ambientales, emocionales y dietéticas, alergias reportadas, planta seleccionada.</li>
          <li><span className="font-semibold">Datos de retroalimentación (feedback):</span> efectividad percibida del tratamiento, efectos secundarios reportados, tiempo de mejora, comentarios adicionales.</li>
        </ul>
      </section>

      <section>
        <h3 className="text-base font-bold text-emerald-700 mb-2">3. Finalidad del tratamiento</h3>
        <p>Sus datos se utilizan para:</p>
        <ul className="list-disc pl-5 space-y-1">
          <li>Generar recomendaciones personalizadas de plantas medicinales mediante el sistema híbrido de inteligencia artificial (RAG y red neuronal).</li>
          <li>Mejorar la precisión y el funcionamiento del sistema a partir del feedback recibido de forma agregada.</li>
          <li>Elaborar estadísticas internas de uso y desempeño de la Plataforma, siempre de forma agregada y/o anonimizada.</li>
        </ul>
        <p className="mt-2">
          Los datos recopilados a través del uso general de la Plataforma son independientes
          del conjunto de datos formal empleado para la validación académica de la tesis, el
          cual se rige por consentimientos informados específicos y firmados por sus participantes.
        </p>
      </section>

      <section>
        <h3 className="text-base font-bold text-emerald-700 mb-2">4. Base legal y consentimiento</h3>
        <p>
          Sus datos de salud constituyen &quot;datos sensibles&quot; bajo la Ley N.º 29733, Ley de
          Protección de Datos Personales. Por ello, su tratamiento requiere su consentimiento
          previo, informado, expreso e inequívoco, el cual se solicita mediante la casilla de
          verificación presentada al momento del registro en la Plataforma.
        </p>
      </section>

      <section>
        <h3 className="text-base font-bold text-emerald-700 mb-2">5. Terceros involucrados en el tratamiento</h3>
        <p>
          Para generar las respuestas conversacionales y recomendaciones, los datos de su
          consulta (no sus datos de identificación directa como nombre o DNI) se transmiten al
          proveedor de infraestructura de modelos de lenguaje [Groq — verificar y completar
          según los términos de servicio y política de privacidad vigentes del proveedor antes
          de publicar esta página].
        </p>
      </section>

      <section>
        <h3 className="text-base font-bold text-emerald-700 mb-2">6. Plazo de conservación</h3>
        <p>
          Sus datos se conservarán mientras su cuenta permanezca activa en la Plataforma.
          Usted puede solicitar la eliminación de su cuenta y sus datos en cualquier momento a
          través del contacto indicado en la sección 1.
        </p>
      </section>

      <section>
        <h3 className="text-base font-bold text-emerald-700 mb-2">7. Medidas de seguridad</h3>
        <p>
          Se aplican medidas técnicas y organizativas razonables para proteger sus datos
          personales frente a accesos no autorizados, pérdida o alteración, conforme a lo
          establecido en el artículo 16 de la Ley N.º 29733.
        </p>
      </section>

      <section>
        <h3 className="text-base font-bold text-emerald-700 mb-2">8. Sus derechos (ARCO)</h3>
        <p>
          Usted tiene derecho a Acceder, Rectificar, Cancelar y Oponerse al tratamiento de sus
          datos personales en cualquier momento, escribiendo al contacto indicado en la sección 1.
        </p>
      </section>

      <section>
        <h3 className="text-base font-bold text-emerald-700 mb-2">9. Advertencia importante</h3>
        <p>
          La información brindada por la Plataforma tiene fines educativos e informativos. No
          sustituye el diagnóstico, tratamiento o consejo de un profesional de la salud. Ante
          síntomas graves o persistentes, se recomienda acudir a un centro de salud.
        </p>
      </section>
    </div>
  );
};

export default PrivacyPolicyContent;